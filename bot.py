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

# ===== সেটিংস =====
WORK_START_HOUR = 17   # বিকাল ৫টা
WORK_END_HOUR = 5      # সকাল ৫টা
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
        user_data[user_id] = make_new_user(today)
    
    # নতুন দিন হলে রিসেট
    if user_data[user_id].get("date") != today:
        user_data[user_id] = make_new_user(today)

    return user_data[user_id]


def make_new_user(today):
    return {
        "status": "off",
        "start_time": None,
        "activity_start": None,
        "activity_type": None,
        "date": today,
        "eat_count": 0,
        "toilet_count": 0,
        "smoke_count": 0,
        "eat_minutes": 0.0,
        "toilet_minutes": 0.0,
        "smoke_minutes": 0.0,
        "logs": []
    }


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


def get_elapsed_minutes(start_str):
    """শুরুর সময় থেকে এখন পর্যন্ত কত মিনিট"""
    if not start_str:
        return 0.0
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        start = BD_TZ.localize(start)
        seconds = (now_bd() - start).total_seconds()
        return round(max(0, seconds) / 60, 1)
    except Exception as e:
        print("Time calculate error:", e)
        return 0.0


def format_min(m):
    if m < 60:
        return f"{m} মিনিট"
    h = int(m // 60)
    mins = int(m % 60)
    return f"{h} ঘণ্টা {mins} মিনিট"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 স্বাগতম!\nআমি তোমার অ্যাটেন্ডেন্স বট।\nনিচের বাটনগুলো ব্যবহার করো।",
        reply_markup=get_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user = get_user(update.effective_user.id)
    now = now_bd().strftime("%Y-%m-%d %H:%M:%S")

    # ===== কাজ শুরু =====
    if text == "✅ কাজ শুরু":
        if not is_work_time():
            await update.message.reply_text(
                "⚠️ এখন কাজের সময় নয়!\nকাজের সময়: বিকাল ৫টা থেকে সকাল ৫টা পর্যন্ত।",
                reply_markup=get_keyboard()
            )
            return

        if user["status"] != "off":
            await update.message.reply_text("ℹ️ তুমি ইতিমধ্যে কাজ শুরু করেছো।", reply_markup=get_keyboard())
            return

        user["status"] = "working"
        user["start_time"] = now
        user["activity_start"] = None
        user["activity_type"] = None
        user["logs"].append(f"{now} - কাজ শুরু")
        save_data()
        await update.message.reply_text(f"✅ কাজ শুরু হয়েছে!\n🕐 {now}", reply_markup=get_keyboard())
        return

    # ===== আসনে ফিরে আসা =====
    if text == "🔙 আসনে ফিরে আসা":
        if user["status"] == "off":
            await update.message.reply_text("❌ তুমি এখনো কাজ শুরু করোনি।", reply_markup=get_keyboard())
            return

        if user["status"] in ["eating", "toilet", "smoking"] and user.get("activity_start"):
            minutes = get_elapsed_minutes(user["activity_start"])

            if user["status"] == "eating":
                user["eat_minutes"] += minutes
                activity_name = "🍚 খাওয়া"
            elif user["status"] == "toilet":
                user["toilet_minutes"] += minutes
                activity_name = "🚽 টয়লেট"
            else:
                user["smoke_minutes"] += minutes
                activity_name = "🚬 সিগারেট"

            user["logs"].append(f"{now} - {activity_name} শেষ ({minutes} মিনিট)")

            msg = (
                f"✅ আসনে ফিরে এসেছো।\n\n"
                f"{activity_name}য় সময় দিয়েছ: *{format_min(minutes)}*\n\n"
                f"📊 আজকের মোট:\n"
                f"🍚 খাওয়া: {user['eat_count']} বার | {format_min(user['eat_minutes'])}\n"
                f"🚽 টয়লেট: {user['toilet_count']} বার | {format_min(user['toilet_minutes'])}\n"
                f"🚬 সিগারেট: {user['smoke_count']} বার | {format_min(user['smoke_minutes'])}"
            )
        else:
            msg = f"✅ আসনে ফিরে এসেছো।\n🕐 {now}"

        user["status"] = "working"
        user["activity_start"] = None
        user["activity_type"] = None
        save_data()
        await update.message.reply_text(msg, reply_markup=get_keyboard(), parse_mode="Markdown")
        return

    # ===== খাওয়া / টয়লেট / সিগারেট =====
    if text in ["🍚 খাওয়া", "🚽 টয়লেট", "🚬 সিগারেট"]:
        if user["status"] == "off":
            await update.message.reply_text("❌ আগে **কাজ শুরু** করো।", reply_markup=get_keyboard(), parse_mode="Markdown")
            return

        if user["status"] in ["eating", "toilet", "smoking"]:
            await update.message.reply_text("⚠️ আগে আসনে ফিরে আসো, তারপর নতুন বিরতি নাও।", reply_markup=get_keyboard())
            return

        if text == "🍚 খাওয়া":
            if user["eat_count"] >= EAT_LIMIT:
                await update.message.reply_text(f"❌ আজকের খাওয়ার সীমা শেষ! (সর্বোচ্চ {EAT_LIMIT} বার)", reply_markup=get_keyboard())
                return
            user["status"] = "eating"
            user["eat_count"] += 1
            limit = EAT_MINUTES
            name = "খাওয়া"

        elif text == "🚽 টয়লেট":
            if user["toilet_count"] >= TOILET_LIMIT:
                await update.message.reply_text(f"❌ আজকের টয়লেট সীমা শেষ! (সর্বোচ্চ {TOILET_LIMIT} বার)", reply_markup=get_keyboard())
                return
            user["status"] = "toilet"
            user["toilet_count"] += 1
            limit = TOILET_MINUTES
            name = "টয়লেট"

        else:  # সিগারেট
            if user["smoke_count"] >= SMOKE_LIMIT:
                await update.message.reply_text(f"❌ আজকের সিগারেট সীমা শেষ! (সর্বোচ্চ {SMOKE_LIMIT} বার)", reply_markup=get_keyboard())
                return
            user["status"] = "smoking"
            user["smoke_count"] += 1
            limit = SMOKE_MINUTES
            name = "সিগারেট"

        user["activity_start"] = now
        user["activity_type"] = user["status"]
        user["logs"].append(f"{now} - {name} শুরু")
        save_data()

        await update.message.reply_text(
            f"{text} শুরু হয়েছে\n"
            f"⏱️ সময়সীমা: {limit} মিনিট\n"
            f"🕐 {now}\n\n"
            f"সময় শেষ হলে বা আগে ফিরে এসে **আসনে ফিরে আসা** চাপো।",
            reply_markup=get_keyboard()
        )
        return

    # ===== কাজ শেষ =====
    if text == "🏁 কাজ শেষ":
        if user["status"] == "off":
            await update.message.reply_text("❌ তুমি এখনো কাজ শুরু করোনি।", reply_markup=get_keyboard())
            return

        # যদি কোনো বিরতি চলতে থাকে তাহলে সেটার সময় যোগ করে নেয়
        if user["status"] in ["eating", "toilet", "smoking"] and user.get("activity_start"):
            minutes = get_elapsed_minutes(user["activity_start"])
            if user["status"] == "eating":
                user["eat_minutes"] += minutes
            elif user["status"] == "toilet":
                user["toilet_minutes"] += minutes
            else:
                user["smoke_minutes"] += minutes

        total_work = 0.0
        if user.get("start_time"):
            total_work = get_elapsed_minutes(user["start_time"])

        total_break = user["eat_minutes"] + user["toilet_minutes"] + user["smoke_minutes"]
        net_work = max(0.0, total_work - total_break)

        summary = (
            f"🏁 *কাজ শেষ হয়েছে!*\n\n"
            f"🕐 শুরু: `{user.get('start_time')}`\n"
            f"🕐 শেষ: `{now}`\n\n"
            f"⏱ মোট সময়: *{format_min(total_work)}*\n"
            f"✅ নিট কাজ: *{format_min(net_work)}*\n"
            f"⏸ মোট বিরতি: *{format_min(total_break)}*\n\n"
            f"🍚 খাওয়া: {user['eat_count']} বার → {format_min(user['eat_minutes'])}\n"
            f"🚽 টয়লেট: {user['toilet_count']} বার → {format_min(user['toilet_minutes'])}\n"
            f"🚬 সিগারেট: {user['smoke_count']} বার → {format_min(user['smoke_minutes'])}\n\n"
            f"শুভ রাত্রি! 🌙"
        )

        user["status"] = "off"
        user["activity_start"] = None
        user["activity_type"] = None
        user["logs"].append(f"{now} - কাজ শেষ")
        save_data()

        await update.message.reply_text(summary, reply_markup=get_keyboard(), parse_mode="Markdown")
        return

    # ===== স্ট্যাটাস =====
    if text == "📊 স্ট্যাটাস":
        status_map = {
            "working": "🟢 কাজ করছে",
            "eating": "🍚 খাচ্ছে",
            "toilet": "🚽 টয়লেটে",
            "smoking": "🚬 সিগারেট খাচ্ছে",
            "off": "🔴 অফ"
        }

        current = ""
        if user["status"] in ["eating", "toilet", "smoking"] and user.get("activity_start"):
            mins = get_elapsed_minutes(user["activity_start"])
            current = f"\n⏱️ এখন চলছে: {format_min(mins)}"

        total_break = user["eat_minutes"] + user["toilet_minutes"] + user["smoke_minutes"]

        msg = (
            f"📊 *তোমার স্ট্যাটাস*\n\n"
            f"অবস্থা: {status_map.get(user['status'])}{current}\n"
            f"কাজ শুরু: {user.get('start_time') or 'এখনো হয়নি'}\n\n"
            f"🍚 খাওয়া: {user['eat_count']} বার | {format_min(user['eat_minutes'])}\n"
            f"🚽 টয়লেট: {user['toilet_count']} বার | {format_min(user['toilet_minutes'])}\n"
            f"🚬 সিগারেট: {user['smoke_count']} বার | {format_min(user['smoke_minutes'])}\n\n"
            f"⏸ মোট বিরতি: {format_min(total_break)}"
        )
        await update.message.reply_text(msg, reply_markup=get_keyboard(), parse_mode="Markdown")
        return

    # অন্য কিছু চাপলে
    await update.message.reply_text("দয়া করে নিচের বাটনগুলো ব্যবহার করো।", reply_markup=get_keyboard())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("Error:", context.error)


def main():
    if not TOKEN:
        print("TOKEN পাওয়া যায়নি!")
        return

    load_data()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    print("বট চালু হয়েছে...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
