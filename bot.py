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
            "eat_minutes": 0,
            "toilet_minutes": 0,
            "smoke_minutes": 0,
            "logs": []
        }

    # নতুন দিন হলে সব রিসেট
    if user_data[user_id].get("date") != today:
        user_data[user_id] = {
            "status": "off",
            "start_time": None,
            "activity_start": None,
            "date": today,
            "eat_count": 0,
            "toilet_count": 0,
            "smoke_count": 0,
            "eat_minutes": 0,
            "toilet_minutes": 0,
            "smoke_minutes": 0,
            "logs": []
        }

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


def calculate_minutes(start_str):
    """শুরুর সময় থেকে এখন পর্যন্ত কত মিনিট হিসাব করে"""
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        start = BD_TZ.localize(start)
        elapsed = (now_bd() - start).total_seconds() / 60
        return round(elapsed, 1)
    except:
        return 0


def check_timeout(user):
    if not user.get("activity_start") or user["status"] in ["working", "off"]:
        return None

    elapsed = calculate_minutes(user["activity_start"])

    if user["status"] == "eating" and elapsed > EAT_MINUTES:
        return f"⚠️ খাওয়ার সময়সীমা ({EAT_MINUTES} মিনিট) শেষ! আসনে ফিরে আসুন।"
    if user["status"] == "toilet" and elapsed > TOILET_MINUTES:
        return f"⚠️ টয়লেটের সময়সীমা ({TOILET_MINUTES} মিনিট) শেষ! আসনে ফিরে আসুন।"
    if user["status"] == "smoking" and elapsed > SMOKE_MINUTES:
        return f"⚠️ সিগারেটের সময়সীমা ({SMOKE_MINUTES} মিনিট) শেষ! আসনে ফিরে আসুন।"
    return None


def format_time(minutes):
    """মিনিটকে ঘণ্টা:মিনিট ফরম্যাটে দেখায়"""
    if minutes < 60:
        return f"{minutes} মিনিট"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours} ঘণ্টা {mins} মিনিট"


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

    # টাইমআউট সতর্কতা
    warning = check_timeout(user)
    if warning and text not in ["🔙 আসনে ফিরে আসা", "🏁 কাজ শেষ"]:
        await update.message.reply_text(warning, reply_markup=get_keyboard())

    # ===== কাজ শুরু =====
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

    # ===== আসনে ফিরে আসা =====
    elif text == "🔙 আসনে ফিরে আসা":
        if user["status"] in ["eating", "toilet", "smoking"] and user.get("activity_start"):
            minutes = calculate_minutes(user["activity_start"])

            if user["status"] == "eating":
                user["eat_minutes"] += minutes
                msg = f"✅ আসনে ফিরে এসেছো।\n🍚 খাওয়ায় সময় দিয়েছ: *{format_time(minutes)}*\n🕐 {now}"
            elif user["status"] == "toilet":
                user["toilet_minutes"] += minutes
                msg = f"✅ আসনে ফিরে এসেছো।\n🚽 টয়লেটে সময় দিয়েছ: *{format_time(minutes)}*\n🕐 {now}"
            elif user["status"] == "smoking":
                user["smoke_minutes"] += minutes
                msg = f"✅ আসনে ফিরে এসেছো।\n🚬 সিগারেটে সময় দিয়েছ: *{format_time(minutes)}*\n🕐 {now}"

            user["logs"].append(f"{now} - আসনে ফিরে এসেছে ({minutes} মিনিট)")
        else:
            msg = f"✅ আসনে ফিরে এসেছো।\n🕐 {now}"

        user["status"] = "working"
        user["activity_start"] = None
        save_data()
        await update.message.reply_text(msg, reply_markup=get_keyboard(), parse_mode="Markdown")

    # ===== খাওয়া =====
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
        user["logs"].append(f"{now} - খাওয়া শুরু ({user['eat_count']}/{EAT_LIMIT})")
        save_data()
        await update.message.reply_text(
            f"🍚 খাওয়া শুরু হয়েছে\n⏱️ সময়সীমা: {EAT_MINUTES} মিনিট\n📊 আজ: {user['eat_count']}/{EAT_LIMIT} বার\n🕐 {now}",
            reply_markup=get_keyboard()
        )

    # ===== টয়লেট =====
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
            f"🚽 টয়লেট\n⏱️ সময়সীমা: {TOILET_MINUTES} মিনিট\n📊 আজ: {user['toilet_count']}/{TOILET_LIMIT} বার\n🕐 {now}",
            reply_markup=get_keyboard()
        )

    # ===== সিগারেট =====
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
            f"🚬 সিগারেট বিরতি\n⏱️ সময়সীমা: {SMOKE_MINUTES} মিনিট\n📊 আজ: {user['smoke_count']}/{SMOKE_LIMIT} বার\n🕐 {now}",
            reply_markup=get_keyboard()
        )

    # ===== কাজ শেষ =====
    elif text == "🏁 কাজ শেষ":
        # যদি কোনো অ্যাক্টিভিটি চলতে থাকে তাহলে সেটার সময়ও যোগ করে নেয়
        if user["status"] in ["eating", "toilet", "smoking"] and user.get("activity_start"):
            minutes = calculate_minutes(user["activity_start"])
            if user["status"] == "eating":
                user["eat_minutes"] += minutes
            elif user["status"] == "toilet":
                user["toilet_minutes"] += minutes
            elif user["status"] == "smoking":
                user["smoke_minutes"] += minutes

        # মোট কাজের সময় হিসাব
        total_work_minutes = 0
        if user.get("start_time"):
            total_work_minutes = calculate_minutes(user["start_time"])

        total_break = user["eat_minutes"] + user["toilet_minutes"] + user["smoke_minutes"]
        net_work = max(0, total_work_minutes - total_break)

        summary = (
            f"🏁 *কাজ শেষ হয়েছে!*\n\n"
            f"🕐 কাজ শুরু: `{user.get('start_time') or 'N/A'}`\n"
            f"🕐 কাজ শেষ: `{now}`\n\n"
            f"⏱ *মোট সময়:* {format_time(total_work_minutes)}\n"
            f"✅ *নিট কাজ:* {format_time(net_work)}\n"
            f"⏸ *মোট বিরতি:* {format_time(total_break)}\n\n"
            f"🍚 খাওয়া: {user['eat_count']} বার | {format_time(user['eat_minutes'])}\n"
            f"🚽 টয়লেট: {user['toilet_count']} বার | {format_time(user['toilet_minutes'])}\n"
            f"🚬 সিগারেট: {user['smoke_count']} বার | {format_time(user['smoke_minutes'])}\n\n"
            f"শুভ রাত্রি! 🌙"
        )

        user["status"] = "off"
        user["activity_start"] = None
        user["logs"].append(f"{now} - কাজ শেষ")
        save_data()

        await update.message.reply_text(summary, reply_markup=get_keyboard(), parse_mode="Markdown")

    # ===== স্ট্যাটাস =====
    elif text == "📊 স্ট্যাটাস":
        status_map = {
            "working": "🟢 কাজ করছে",
            "eating": "🍚 খাচ্ছে",
            "toilet": "🚽 টয়লেটে",
            "smoking": "🚬 সিগারেট খাচ্ছে",
            "off": "🔴 অফ"
        }

        current_activity = ""
        if user["status"] in ["eating", "toilet", "smoking"] and user.get("activity_start"):
            mins = calculate_minutes(user["activity_start"])
            current_activity = f"\n⏱️ চলমান: {format_time(mins)}"

        total_break = user["eat_minutes"] + user["toilet_minutes"] + user["smoke_minutes"]

        msg = (
            f"📊 *বর্তমান স্ট্যাটাস*\n\n"
            f"অবস্থা: {status_map.get(user['status'])}{current_activity}\n"
            f"কাজ শুরু: {user.get('start_time') or 'এখনো শুরু হয়নি'}\n\n"
            f"🍚 খাওয়া: {user['eat_count']}/{EAT_LIMIT} বার | {format_time(user['eat_minutes'])}\n"
            f"🚽 টয়লেট: {user['toilet_count']}/{TOILET_LIMIT} বার | {format_time(user['toilet_minutes'])}\n"
            f"🚬 সিগারেট: {user['smoke_count']}/{SMOKE_LIMIT} বার | {format_time(user['smoke_minutes'])}\n\n"
            f"⏸ মোট বিরতি: {format_time(total_break)}"
        )
        await update.message.reply_text(msg, reply_markup=get_keyboard(), parse_mode="Markdown")

    else:
        await update.message.reply_text("দয়া করে নিচের বাটন ব্যবহার করো।", reply_markup=get_keyboard())


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
