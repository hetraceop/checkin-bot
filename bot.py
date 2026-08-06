from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import json
import os
import pytz

TOKEN = os.getenv("TOKEN")
DATA_FILE = "checkin_data.json"
user_data = {}

# বাংলাদেশ সময়
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
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            user_data = json.load(f)

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

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
        user_data[user_id].update({
            "date": today,
            "eat_count": 0,
            "toilet_count": 0,
            "smoke_count": 0,
            "logs": [],
            "start_time": None,
            "activity_start": None,
            "status": "off"
        })
    
    return user_data[user_id]

def get_keyboard():
    keyboard = [
        [KeyboardButton("✅ কাজ শুরু"), KeyboardButton("🔙 আসনে ফিরে আসা")],
        [KeyboardButton("🍚 খাওয়া"), KeyboardButton("🚽 টয়লেট")],
        [KeyboardButton("🚬 সিগারেট"), KeyboardButton("🏁 কাজ শেষ")],
        [KeyboardButton("📊 স্ট্যাটাস")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def is_work_time():
    hour = now_bd().hour
    return hour >= WORK_START_HOUR or hour < WORK_END_HOUR

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 স্বাগতম!\n\n"
        "আমি তোমার অ্যাটেন্ডেন্স বট।\n"
        "নিচের বাটনগুলো দিয়ে চেক-ইন করো।\n\n"
        "⏰ কাজের সময়: বিকাল ৫টা – সকাল ৫টা",
        reply_markup=get_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = get_user(update.effective_user.id)
    now = now_bd().strftime("%Y-%m-%d %H:%M:%S")
    
    if text == "✅ কাজ শুরু":
        if not is_work_time():
            await update.message.reply_text(
                "❌ এখন কাজের সময় নয়।\n"
                "কাজের সময়: বিকাল ৫টা থেকে সকাল ৫টা পর্যন্ত",
                reply_markup=get_keyboard()
            )
            return
        if user["status"] == "working":
            await update.message.reply_text("ℹ️ তুমি ইতিমধ্যে কাজ শুরু করেছো।", reply_markup=get_keyboard())
            return
        
        user["status"] = "working"
        user["start_time"] = now
        user["activity_start"] = None
        user["logs"].append(f"{now} - কাজ শুরু")
        save_data()
        await update.message.reply_text(
            f"✅ *কাজ শুরু হয়েছে!*\n\n"
            f"🕐 সময়: `{now}`\n"
            f"🟢 স্ট্যাটাস: কাজ করছে",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

    elif text == "🔙 আসনে ফিরে আসা":
        user["status"] = "working"
        user["activity_start"] = None
        user["logs"].append(f"{now} - আসনে ফিরে এসেছে")
        save_data()
        await update.message.reply_text(
            f"✅ *আসনে ফিরে এসেছো*\n\n🕐 সময়: `{now}`",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

    elif text == "🍚 খাওয়া":
        if user["eat_count"] >= EAT_LIMIT:
            await update.message.reply_text(f"❌ আজকের খাওয়ার সীমা শেষ!\nসর্বোচ্চ {EAT_LIMIT} বার", reply_markup=get_keyboard())
            return
        user["status"] = "eating"
        user["activity_start"] = now
        user["eat_count"] += 1
        user["logs"].append(f"{now} - খাওয়া ({user['eat_count']}/{EAT_LIMIT})")
        save_data()
        await update.message.reply_text(
            f"🍚 *খাওয়া শুরু*\n\n"
            f"⏱️ সময়সীমা: {EAT_MINUTES} মিনিট\n"
            f"📊 আজ: {user['eat_count']}/{EAT_LIMIT} বার\n"
            f"🕐 `{now}`",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

    elif text == "🚽 টয়লেট":
        if user["toilet_count"] >= TOILET_LIMIT:
            await update.message.reply_text(f"❌ আজকের টয়লেট সীমা শেষ!\nসর্বোচ্চ {TOILET_LIMIT} বার", reply_markup=get_keyboard())
            return
        user["status"] = "toilet"
        user["activity_start"] = now
        user["toilet_count"] += 1
        user["logs"].append(f"{now} - টয়লেট ({user['toilet_count']}/{TOILET_LIMIT})")
        save_data()
        await update.message.reply_text(
            f"🚽 *টয়লেট*\n\n"
            f"⏱️ সময়সীমা: {TOILET_MINUTES} মিনিট\n"
            f"📊 আজ: {user['toilet_count']}/{TOILET_LIMIT} বার\n"
            f"🕐 `{now}`",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

    elif text == "🚬 সিগারেট":
        if user["smoke_count"] >= SMOKE_LIMIT:
            await update.message.reply_text(f"❌ আজকের সিগারেট সীমা শেষ!\nসর্বোচ্চ {SMOKE_LIMIT} বার", reply_markup=get_keyboard())
            return
        user["status"] = "smoking"
        user["activity_start"] = now
        user["smoke_count"] += 1
        user["logs"].append(f"{now} - সিগারেট ({user['smoke_count']}/{SMOKE_LIMIT})")
        save_data()
        await update.message.reply_text(
            f"🚬 *সিগারেট বিরতি*\n\n"
            f"⏱️ সময়সীমা: {SMOKE_MINUTES} মিনিট\n"
            f"📊 আজ: {user['smoke_count']}/{SMOKE_LIMIT} বার\n"
            f"🕐 `{now}`",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

    elif text == "🏁 কাজ শেষ":
        user["status"] = "off"
        user["activity_start"] = None
        user["logs"].append(f"{now} - কাজ শেষ")
        save_data()
        await update.message.reply_text(
            f"🏁 *কাজ শেষ হয়েছে!*\n\n"
            f"🕐 সময়: `{now}`\n"
            f"শুভ রাত্রি!",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

    elif text == "📊 স্ট্যাটাস":
        status_map = {
            "working": "🟢 কাজ করছে",
            "eating": "🍚 খাচ্ছে",
            "toilet": "🚽 টয়লেটে",
            "smoking": "🚬 সিগারেট খাচ্ছে",
            "off": "🔴 অফ"
        }
        msg = (
            f"📊 *তোমার স্ট্যাটাস*\n\n"
            f"অবস্থা: {status_map.get(user['status'])}\n"
            f"কাজ শুরু: `{user.get('start_time', 'এখনো শুরু হয়নি')}`\n\n"
            f"🍚 খাওয়া: {user['eat_count']}/{EAT_LIMIT}\n"
            f"🚽 টয়লেট: {user['toilet_count']}/{TOILET_LIMIT}\n"
            f"🚬 সিগারেট: {user['smoke_count']}/{SMOKE_LIMIT}"
        )
        await update.message.reply_text(msg, reply_markup=get_keyboard(), parse_mode="Markdown")

    else:
        await update.message.reply_text("দয়া করে নিচের বাটন ব্যবহার করো।", reply_markup=get_keyboard())

def main():
    load_data()

    if not TOKEN:
        raise ValueError("TOKEN environment variable is missing!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("বট চালু হয়েছে...")
    app.run_polling()

if __name__ == "__main__":
    main()
