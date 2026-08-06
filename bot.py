from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import json
import os

TOKEN = os.getenv("TOKEN")

DATA_FILE = "checkin_data.json"
user_data = {}

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
    if user_id not in user_data:
        user_data[user_id] = {
            "status": "off",
            "start_time": None,
            "logs": []
        }
    return user_data[user_id]

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("কাজ শুরু"), KeyboardButton("আসনে ফিরে আসা")],
        [KeyboardButton("খাওয়া"), KeyboardButton("টয়লেট")],
        [KeyboardButton("সিগারেট"), KeyboardButton("কাজ শেষ")],
        [KeyboardButton("স্ট্যাটাস")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "স্বাগতম! আমি চেক-ইন বট।\nনিচের বাটনগুলো ব্যবহার করো:",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = get_user(update.effective_user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if text == "কাজ শুরু":
        if user["status"] == "working":
            await update.message.reply_text("তুমি ইতিমধ্যে কাজ শুরু করেছো!")
            return
        user["status"] = "working"
        user["start_time"] = now
        user["logs"].append(f"{now} - কাজ শুরু")
        save_data()
        await update.message.reply_text(f"✅ কাজ শুরু হয়েছে!\nসময়: {now}", reply_markup=get_main_keyboard())

    elif text == "আসনে ফিরে আসা":
        user["status"] = "working"
        user["logs"].append(f"{now} - আসনে ফিরে এসেছে")
        save_data()
        await update.message.reply_text(f"✅ আসনে ফিরে এসেছো\nসময়: {now}", reply_markup=get_main_keyboard())

    elif text == "খাওয়া":
        user["status"] = "eating"
        user["logs"].append(f"{now} - খাওয়া শুরু")
        save_data()
        await update.message.reply_text(f"🍚 খাওয়া শুরু\nসময়: {now}", reply_markup=get_main_keyboard())

    elif text == "টয়লেট":
        user["status"] = "toilet"
        user["logs"].append(f"{now} - টয়লেট")
        save_data()
        await update.message.reply_text(f"🚽 টয়লেট\nসময়: {now}", reply_markup=get_main_keyboard())

    elif text == "সিগারেট":
        user["status"] = "smoking"
        user["logs"].append(f"{now} - সিগারেট")
        save_data()
        await update.message.reply_text(f"🚬 সিগারেট বিরতি\nসময়: {now}", reply_markup=get_main_keyboard())

    elif text == "কাজ শেষ":
        user["status"] = "off"
        user["logs"].append(f"{now} - কাজ শেষ")
        save_data()
        await update.message.reply_text(f"🏁 কাজ শেষ!\nসময়: {now}", reply_markup=get_main_keyboard())

    elif text == "স্ট্যাটাস":
        status_map = {
            "working": "কাজ করছে",
            "eating": "খাচ্ছে",
            "toilet": "টয়লেটে",
            "smoking": "সিগারেট খাচ্ছে",
            "off": "অফ"
        }
        await update.message.reply_text(
            f"📊 তোমার স্ট্যাটাস: {status_map.get(user['status'], user['status'])}\n"
            f"শুরুর সময়: {user.get('start_time', 'নেই')}",
            reply_markup=get_main_keyboard()
        )

    else:
        await update.message.reply_text("দয়া করে নিচের বাটনগুলো ব্যবহার করো।", reply_markup=get_main_keyboard())

def main():
    load_data()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_message))

    print("বট চালু হয়েছে...")
    app.run_polling()

if __name__ == "__main__":
    main()
