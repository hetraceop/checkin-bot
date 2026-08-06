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


def make_new_user(today):
    return {
        "status": "off",
        "start_time": None,
        "activity_start": None,
        "date": today,
        "eat_count": 0,
        "toilet_count": 0,
        "smoke_count": 0,
        "eat_minutes": 0.0,
        "toilet_minutes": 0.0,
        "smoke_minutes": 0.0,
    }


def get_user(user_id):
    user_id = str(user_id)
    today = now_bd().strftime("%Y-%m-%d")

    if user_id not in user_data:
        user_data[user_id] = make_new_user(today)

    if user_data[user_id].get("date") != today:
        user_data[user_id] = make_new_user(today)

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


def get_minutes(start_str):
    if not start_str:
        return 0.0
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        start = BD_TZ.localize(start)
        return round(max(0, (now_bd() - start).total_seconds()) / 60, 1)
    except:
        return 0.0


def format_min(m):
    if m < 60:
        return f"{m} মিনিট"
    return f"{int(m // 60)} ঘণ্টা {int(m % 60)} মিনিট"


def close_current_activity(user):
    if user["status"] not in ["eating", "toilet", "smoking"] or not user.get("activity_start"):
        return 0.0

    minutes = get_minutes(user["activity_start"])

    if user["status"] == "eating":
        user["eat_minutes"] += minutes
    elif user["status"] == "toilet":
        user["toilet_minutes"] += minutes
    elif user["status"] == "smoking":
        user["smoke_minutes"] += minutes

    user["activity_start"] = None
    return minutes


def check_overtime(user):
    """বিরতির সময়সীমা অতিক্রম করলে ওয়ার্নিং"""
    if user["status"] not in ["eating", "toilet", "smoking"] or not user.get("activity_start"):
        return None

    elapsed = get_minutes(user["activity_start"])

    if user["status"] == "eating" and elapsed > EAT_MINUTES:
        return f"⚠️ সতর্কতা!\nখাওয়ার সময়সীমা ({EAT_MINUTES} মিনিট) শেষ হয়ে গেছে।\nএখন পর্যন্ত: {format_min(elapsed)}"
    if user["status"] == "toilet" and elapsed > TOILET_MINUTES:
        return f"⚠️ সতর্কতা!\nটয়লেটের সময়সীমা ({TOILET_MINUTES} মিনিট) শেষ হয়ে গেছে।\nএখন পর্যন্ত: {format_min(elapsed)}"
    if user["status"] == "smoking" and elapsed > SMOKE_MINUTES:
        return f"⚠️ সতর্কতা!\nসিগারেটের সময়সীমা ({SMOKE_MINUTES} মিনিট) শেষ হয়ে গেছে।\nএখন পর্যন্ত: {format_min(elapsed)}"
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 স্বাগতম!\nনিচের বাটন ব্যবহার করো।",
        reply_markup=get_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user = get_user(update.effective_user.id)
    now = now_bd().strftime("%Y-%m-%d %H:%M:%S")

    # প্রথমে ওভারটাইম চেক
    overtime_msg = check_overtime(user)
    if overtime_msg and text not in ["🔙 আসনে ফিরে আসা", "🏁 কাজ শেষ"]:
        await update.message.reply_text(overtime_msg, reply_markup=get_keyboard())
        # ওয়ার্নিং দিয়েও কাজ চালিয়ে যাবে, ব্লক করব না

    # ===== কাজ শুরু =====
    if text == "✅ কাজ শুরু":
        if not is_work_time():
            await update.message.reply_text(
                "⚠️ *কাজের সময় নয়!*\n\n"
                "কাজ শুরু করা যাবে শুধুমাত্র\nবিকাল ৫টা থেকে সকাল ৫টার মধ্যে।",
                reply_markup=get_keyboard(),
                parse_mode="Markdown"
            )
            return

        if user["status"] != "off":
            await update.message.reply_text(
                "⚠️ তুমি *ইতিমধ্যে* কাজ শুরু করেছো।\nআবার চাপার দরকার নেই।",
                reply_markup=get_keyboard(),
                parse_mode="Markdown"
            )
            return

        user["status"] = "working"
        user["start_time"] = now
        user["activity_start"] = None
        save_data()
        await update.message.reply_text(f"✅ কাজ শুরু হয়েছে!\n🕐 {now}", reply_markup=get_keyboard())
        return

    # ===== আসনে ফিরে আসা =====
    if text == "🔙 আসনে ফিরে আসা":
        if user["status"] == "off":
            await update.message.reply_text("⚠️ আগে কাজ শুরু করো।", reply_markup=get_keyboard())
            return

        if user["status"] == "working":
            await update.message.reply_text(
                "ℹ️ তুমি ইতিমধ্যে আসনে আছো।\nকোনো বিরতি চলছে না।",
                reply_markup=get_keyboard()
            )
            return

        minutes = close_current_activity(user)
        user["status"] = "working"
        save_data()

        msg = (
            f"✅ আসনে ফিরে এসেছো\n"
            f"⏱️ এবারের বিরতি: *{format_min(minutes)}*\n\n"
            f"📊 আজকের মোট:\n"
            f"🍚 খাওয়া: {user['eat_count']} বার | {format_min(user['eat_minutes'])}\n"
            f"🚽 টয়লেট: {user['toilet_count']} বার | {format_min(user['toilet_minutes'])}\n"
            f"🚬 সিগারেট: {user['smoke_count']} বার | {format_min(user['smoke_minutes'])}"
        )
        await update.message.reply_text(msg, reply_markup=get_keyboard(), parse_mode="Markdown")
        return

    # ===== খাওয়া / টয়লেট / সিগারেট =====
    if text in ["🍚 খাওয়া", "🚽 টয়লেট", "🚬 সিগারেট"]:
        if user["status"] == "off":
            await update.message.reply_text("⚠️ আগে **কাজ শুরু** করো।", reply_markup=get_keyboard(), parse_mode="Markdown")
            return

        # একই বাটন আবার চাপলে
        if (text == "🍚 খাওয়া" and user["status"] == "eating") or \
           (text == "🚽 টয়লেট" and user["status"] == "toilet") or \
           (text == "🚬 সিগারেট" and user["status"] == "smoking"):
            elapsed = get_minutes(user["activity_start"])
            await update.message.reply_text(
                f"⚠️ তুমি *ইতিমধ্যে* এই বিরতিতে আছো।\n"
                f"এখন পর্যন্ত: {format_min(elapsed)}\n\n"
                f"ফিরে আসতে চাইলে **আসনে ফিরে আসা** চাপো।",
                reply_markup=get_keyboard(),
                parse_mode="Markdown"
            )
            return

        # আগের অ্যাক্টিভিটি বন্ধ করে
        prev_minutes = close_current_activity(user)

        if text == "🍚 খাওয়া":
            if user["eat_count"] >= EAT_LIMIT:
                await update.message.reply_text(f"❌ খাওয়ার সীমা শেষ! (সর্বোচ্চ {EAT_LIMIT} বার)", reply_markup=get_keyboard())
                return
            user["status"] = "eating"
            user["eat_count"] += 1
            limit = EAT_MINUTES
            icon = "🍚"

        elif text == "🚽 টয়লেট":
            if user["toilet_count"] >= TOILET_LIMIT:
                await update.message.reply_text(f"❌ টয়লেট সীমা শেষ! (সর্বোচ্চ {TOILET_LIMIT} বার)", reply_markup=get_keyboard())
                return
            user["status"] = "toilet"
            user["toilet_count"] += 1
            limit = TOILET_MINUTES
            icon = "🚽"

        else:
            if user["smoke_count"] >= SMOKE_LIMIT:
                await update.message.reply_text(f"❌ সিগারেট সীমা শেষ! (সর্বোচ্চ {SMOKE_LIMIT} বার)", reply_markup=get_keyboard())
                return
            user["status"] = "smoking"
            user["smoke_count"] += 1
            limit = SMOKE_MINUTES
            icon = "🚬"

        user["activity_start"] = now
        save_data()

        extra = f"\n(আগের বিরতি যোগ হয়েছে: {format_min(prev_minutes)})" if prev_minutes > 0 else ""
        await update.message.reply_text(
            f"{icon} {text} শুরু হয়েছে\n⏱️ সময়সীমা: {limit} মিনিট\n🕐 {now}{extra}",
            reply_markup=get_keyboard()
        )
        return

    # ===== কাজ শেষ =====
    if text == "🏁 কাজ শেষ":
        if user["status"] == "off":
            await update.message.reply_text(
                "⚠️ তুমি কাজ শুরু করোনি।\nআগে **কাজ শুরু** করো।",
                reply_markup=get_keyboard(),
                parse_mode="Markdown"
            )
            return

        close_current_activity(user)

        total_work = get_minutes(user["start_time"]) if user.get("start_time") else 0.0
        total_break = user["eat_minutes"] + user["toilet_minutes"] + user["smoke_minutes"]
        net_work = max(0.0, total_work - total_break)

        summary = (
            f"🏁 *কাজ শেষ!*\n\n"
            f"🕐 শুরু: {user.get('start_time')}\n"
            f"🕐 শেষ: {now}\n\n"
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
        save_data()

        await update.message.reply_text(summary, reply_markup=get_keyboard(), parse_mode="Markdown")
        return

    # ===== স্ট্যাটাস =====
    if text == "📊 স্ট্যাটাস":
        status_text = {
            "working": "🟢 কাজ করছে",
            "eating": "🍚 খাচ্ছে",
            "toilet": "🚽 টয়লেটে",
            "smoking": "🚬 সিগারেট",
            "off": "🔴 অফ"
        }.get(user["status"], user["status"])

        current = ""
        if user["status"] in ["eating", "toilet", "smoking"] and user.get("activity_start"):
            current = f"\n⏱️ চলমান: {format_min(get_minutes(user['activity_start']))}"

        total_break = user["eat_minutes"] + user["toilet_minutes"] + user["smoke_minutes"]

        msg = (
            f"📊 *স্ট্যাটাস*\n\n"
            f"অবস্থা: {status_text}{current}\n"
            f"কাজ শুরু: {user.get('start_time') or 'এখনো হয়নি'}\n\n"
            f"🍚 খাওয়া: {user['eat_count']} বার | {format_min(user['eat_minutes'])}\n"
            f"🚽 টয়লেট: {user['toilet_count']} বার | {format_min(user['toilet_minutes'])}\n"
            f"🚬 সিগারেট: {user['smoke_count']} বার | {format_min(user['smoke_minutes'])}\n\n"
            f"⏸ মোট বিরতি: {format_min(total_break)}"
        )
        await update.message.reply_text(msg, reply_markup=get_keyboard(), parse_mode="Markdown")
        return

    await update.message.reply_text("দয়া করে নিচের বাটন ব্যবহার করো।", reply_markup=get_keyboard())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("Error:", context.error)


def main():
    if not TOKEN:
        print("TOKEN নেই!")
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
