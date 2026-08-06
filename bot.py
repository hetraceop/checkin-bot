from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "স্বাগতম! আমি চেক-ইন বট।\n\n"
        "/work - কাজ শুরু\n"
        "/back - আসনে ফিরে আসা\n"
        "/eat - খাওয়া\n"
        "/wc - টয়লেট\n"
        "/smoke - সিগারেট\n"
        "/offwork - কাজ শেষ\n"
        "/status - স্ট্যাটাস দেখো"
    )

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if user["status"] == "working":
        await update.message.reply_text("তুমি ইতিমধ্যে কাজ শুরু করেছো!")
        return
    
    user["status"] = "working"
    user["start_time"] = now
    user["logs"].append(f"{now} - কাজ শুরু")
    save_data()
    
    await update.message.reply_text(f"কাজ শুরু হয়েছে!\nসময়: {now}")

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    user["status"] = "working"
    user["logs"].append(f"{now} - আসনে ফিরে এসেছে")
    save_data()
    
    await update.message.reply_text(f"আসনে ফিরে এসেছো\nসময়: {now}")

async def eat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    user["status"] = "eating"
    user["logs"].append(f"{now} - খাওয়া শুরু")
    save_data()
    
    await update.message.reply_text(f"খাওয়া শুরু\nসময়: {now}")

async def wc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    user["status"] = "toilet"
    user["logs"].append(f"{now} - টয়লেট")
    save_data()
    
    await update.message.reply_text(f"টয়লেট\nসময়: {now}")

async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    user["status"] = "smoking"
    user["logs"].append(f"{now} - সিগারেট")
    save_data()
    
    await update.message.reply_text(f"সিগারেট বিরতি\nসময়: {now}")

async def offwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    user["status"] = "off"
    user["logs"].append(f"{now} - কাজ শেষ")
    save_data()
    
    await update.message.reply_text(f"কাজ শেষ!\nসময়: {now}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    status_map = {
        "working": "কাজ করছে",
        "eating": "খাচ্ছে",
        "toilet": "টয়লেটে",
        "smoking": "সিগারেট খাচ্ছে",
        "off": "অফ"
    }
    await update.message.reply_text(
        f"তোমার স্ট্যাটাস: {status_map.get(user['status'], user['status'])}\n"
        f"শুরুর সময়: {user.get('start_time', 'নেই')}"
    )

def main():
    load_data()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("work", work))
    app.add_handler(CommandHandler("back", back))
    app.add_handler(CommandHandler("eat", eat))
    app.add_handler(CommandHandler("wc", wc))
    app.add_handler(CommandHandler("smoke", smoke))
    app.add_handler(CommandHandler("offwork", offwork))
    app.add_handler(CommandHandler("status", status))
    
    print("বট চালু হয়েছে...")
    app.run_polling()

if __name__ == "__main__":
    main()
