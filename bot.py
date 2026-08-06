from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import json
import os
import pytz

TOKEN = os.getenv("TOKEN")
DATA_FILE = "/tmp/checkin_data.json"
user_data = {}

BD_TZ = pytz.timezone("Asia/Dhaka")

WORK_START_HOUR = 17
WORK_END_HOUR = 5
EAT_LIMIT = 2
EAT_MINUTES = 40
TOILET_LIMIT = 4
TOILET_MINUTES = 15
SMOKE_LIMIT = 6
SMOKE_MINUTES = 10


def now_bd():
    return datetime.now(BD_TZ)


def load_data():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except:
            user_data = {}


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Save error:", e)


def get_user(user_id):
    user_id = str(user_id)
    today = now_bd().strftime("%Y-%m-%d")

    if user_id not in user_data:
        user_data[user_id] = {
            "status": "off",
            "start_time": None,
            "activity_start": None,
            "date": today,
            "eat_count": 0,
            "toilet_count": 0,
            "smoke_count": 0,
            "logs": []
        }

    if user_data[user_id].get("date") != today:
        user_data[user_id]["date"] = today
        user_data[user_id]["eat_count"] = 0
        user_data[user_id]["toilet_count"] = 0
        user_data[user_id]["smoke_count"] = 0
        user_data[user_id]["logs"] = []
        user_data[user_id]["status"] = "off"
        user_data[user_id]["activity_start"] = None

    return user_data[user_id]


def get_keyboard():
    keyboard = [
        [KeyboardButton("✅ কাজ শুরু"), KeyboardButton("🔙 আসনে ফিরে আসা")],
        [KeyboardButton("🍚 খাওয়া"), KeyboardButton("🚽 টয়লেট")],
        [KeyboardButton("🚬 সিগারেট"), KeyboardButton("🏁 কাজ শেষ")],
        [KeyboardButton("📊 স্ট্যাটাস")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def is_work_time():
    hour = now_bd().hour
    if WORK_START_HOUR > WORK_END_HOUR:
        return hour >= WORK_START_HOUR or hour < WORK_END_HOUR
    return WORK_START_HOUR <= hour < WORK_END_HOUR


def check_timeout(user):
    if not user.get("activity_start") or user["status"] in ["working", "off"]:
        return None
    try:
        start = datetime.strptime(user["activity_start"], "%Y-%m-%d %H:%M:%S")
        start = BD_TZ.localize(start)
        elapsed = (now_bd() - start).total_seconds() / 60
    except:
        return None

    if user["status"] == "eating" and elapsed > EAT_MINUTES:
        return f"⚠️ খাওয়ার সময়সীমা ({EAT_MINUTES} মিনিট) শেষ! আসনে ফিরে আসুন।"
    if user["status"] == "toilet" and elapsed > TOILET_MINUTES:
        return f"⚠️ টয়লেটের সময়সীমা ({TOILET_MINUTES} মিনিট) শেষ! আসনে ফিরে আসুন।"
    if user["status"] == "smoking" and elapsed > SMOKE_MINUTES:
        return f"⚠️ সিগারেটের সময়সীমা ({SMOKE_MINUTES} মিনিট) শেষ! আসনে ফিরে আসুন।"
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 স্বাগতম!\nআমি তোমার অ্যাটেন্ডেন্স বট।\nনিচের বাটন ব্যবহার করো।",
        reply_markup=get_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    user = get_user(update.effective_user.id)
    now = now_bd().strftime("%Y-%m-%d %H:%M:%S")

    warning = check_timeout(user)
    if warning and text not in ["🔙 আসনে ফিরে আসা", "🏁 কাজ শেষ"]:
        await update.message.reply_text(warning, reply_markup=get_keyboard())

    if text == "✅ কাজ শুরু":
        if not is_work_time():
            await update.message.reply_text("❌ এখন কাজের সময় নয়।\nসময়: বিকাল ৫টা – সকাল ৫টা", reply_markup=get_keyboard())
            return
        if user["status"] == "working":
            await update.message.reply_text("ℹ️ তুমি ইতিমধ্যে কাজ শুরু করেছো।", reply_markup=get_keyboard())
            return
        user["status"] = "working"
        user["start_time"] = now
        user["activity_start"] = None
        user["logs"].append(f"{now} - কাজ শুরু")
        save_data()
        await update.message.reply_text(f"✅ কাজ শুরু হয়েছে!\n🕐 {now}", reply_markup=get_keyboard())

    elif text == "🔙 আসনে ফিরে আসা":
        user["status"] = "working"
        user["activity_start"] = None
        user["logs"].append(f"{now} - আসনে ফিরে এসেছে")
        save_data()
        await update.message.reply_text(f"✅ আসনে ফিরে এসেছো।\n🕐 {now}", reply_markup=get_keyboard())

    elif text == "🍚 খাওয়া":
        if user["status"] == "off":
            await update.message.reply_text("❌ আগে কাজ শুরু করো।", reply_markup=get_keyboard())
            return
        if user["eat_count"] >= EAT_LIMIT:
            await update.message.reply_text(f"❌ আজকের খাওয়ার সীমা শেষ! ({EAT_LIMIT} বার)", reply_markup=get_keyboard())
            return
        user["status"] = "eating"
        user["activity_start"] = now
        user["eat_count"] += 1
        user["logs"].append(f"{now} - খাওয়া ({user['eat_count']}/{EAT_LIMIT})")
        save_data()
        await update.message.reply_text(
            f"🍚 খাওয়া শুরু\n⏱️ {EAT_MINUTES} মিনিট\n📊 {user['eat_count']}/{EAT_LIMIT}\n🕐 {now}",
            reply_markup=get_keyboard()
        )

    elif text == "🚽 টয়লেট":
        if user["status"] == "off":
            await update.message.reply_text("❌ আগে কাজ শুরু করো।", reply_markup=get_keyboard())
            return
        if user["toilet_count"] >= TOILET_LIMIT:
            await update.message.reply_text(f"❌ আজকের টয়লেট সীমা শেষ! ({TOILET_LIMIT} বার)", reply_markup=get_keyboard())
            return
        user["status"] = "toilet"
        user["activity_start"] = now
        user["toilet_count"] += 1
        user["logs"].append(f"{now} - টয়লেট ({user['toilet_count']}/{TOILET_LIMIT})")
        save_data()
        await update.message.reply_text(
            f"🚽 টয়লেট\n⏱️ {TOILET_MINUTES} মিনিট\n📊 {user['toilet_count']}/{TOILET_LIMIT}\n🕐 {now}",
            reply_markup=get_keyboard()
        )

    elif text == "🚬 সিগারেট":
        if user["status"] == "off":
            await update.message.reply_text("❌ আগে কাজ শুরু করো।", reply_markup=get_keyboard())
            return
        if user["smoke_count"] >= SMOKE_LIMIT:
            await update.message.reply_text(f"❌ আজকের সিগারেট সীমা শেষ! ({SMOKE_LIMIT} বার)", reply_markup=get_keyboard())
            return
        user["status"] = "smoking"
        user["activity_start"] = now
        user["smoke_count"] += 1
        user["logs"].append(f"{now} - সিগারেট ({user['smoke_count']}/{SMOKE_LIMIT})")
        save_data()
        await update.message.reply_text(
            f"🚬 সিগারেট\n⏱️ {SMOKE_MINUTES} মিনিট\n📊 {user['smoke_count']}/{SMOKE_LIMIT}\n🕐 {now}",
            reply_markup=get_keyboard()
        )

    elif text == "🏁 কাজ শেষ":
        user["status"] = "off"
        user["activity_start"] = None
        user["logs"].append(f"{now} - কাজ শেষ")
        save_data()
        await update.message.reply_text(f"🏁 কাজ শেষ!\n🕐 {now}\nশুভ রাত্রি!", reply_markup=get_keyboard())

    elif text == "📊 স্ট্যাটাস":
        status_map = {
            "working": "🟢 কাজ করছে",
            "eating": "🍚 খাচ্ছে",
            "toilet": "🚽 টয়লেটে",
            "smoking": "🚬 সিগারেট",
            "off": "🔴 অফ"
        }
        msg = (
            f"📊 *স্ট্যাটাস*\n\n"
            f"অবস্থা: {status_map.get(user['status'])}\n"
            f"কাজ শুরু: {user.get('start_time') or 'এখনো হয়নি'}\n\n"
            f"🍚 খাওয়া: {user['eat_count']}/{EAT_LIMIT}\n"
            f"🚽 টয়লেট: {user['toilet_count']}/{TOILET_LIMIT}\n"
            f"🚬 সিগারেট: {user['smoke_count']}/{SMOKE_LIMIT}"
        )
        await update.message.reply_text(msg, reply_markup=get_keyboard(), parse_mode="Markdown")

    else:
        await update.message.reply_text("দয়া করে বাটন ব্যবহার করো।", reply_markup=get_keyboard())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("Error:", context.error)


def main():
    if not TOKEN:
        print("TOKEN পাওয়া যায়নি!")
        return

    load_data()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    print("বট চালু হয়েছে...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
