from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import json
import os

TOKEN = os.getenv("TOKEN")
DATA_FILE = "checkin_data.json"
user_data = {}

# ===== সেটিংস =====
WORK_START_HOUR = 17   # বিকাল ৫টা
WORK_END_HOUR = 5      # সকাল ৫টা
EAT_LIMIT = 2
EAT_MINUTES = 40
TOILET_LIMIT = 4
TOILET_MINUTES = 15
SMOKE_LIMIT = 6
SMOKE_MINUTES = 10

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
    today = datetime.now().strftime("%Y-%m-%d")
    
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
    
    # নতুন দিন হলে কাউন্টার রিসেট
    if user_data[user_id].get("date") != today:
        user_data[user_id]["date"] = today
        user_data[user_id]["eat_count"] = 0
        user_data[user_id]["toilet_count"] = 0
        user_data[user_id]["smoke_count"] = 0
        user_data[user_id]["logs"] = []
    
    return user_data[user_id]

def get_keyboard():
    keyboard = [
        [KeyboardButton("✅
