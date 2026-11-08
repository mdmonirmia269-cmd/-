import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import requests
import secrets
import time
from flask import Flask, request
import threading

# ==================== কনফিগারেশন ====================
API_TOKEN = os.environ.get("BOT_TOKEN", "9239200994:AAF1CfmE-CA0fHi6rT0CAxam_3vnOo25Yx0")
NP_API = "https://npnetworkbd.cam/api/user"
NP_KEY = os.environ.get("NP_KEY", "NP-6HXU732PNEATGVFM")

bot = telebot.TeleBot(API_TOKEN)

# দেশ কনফিগ
COUNTRY_CONFIG = {
    "South Africa": {"code": "ZA", "range": "277", "flag": "🇿🇦"},
    "Cameroon":     {"code": "CM", "range": "2376", "flag": "🇨🇲"},
    "France":       {"code": "FR", "range": "336", "flag": "🇫🇷"},
    "Uzbekistan":   {"code": "UZ", "range": "9989", "flag": "🇺🇿"},
}

user_sessions = {}

# ==================== API ====================
def np(action: str, body: dict = None) -> dict:
    headers = {
        "mauthapi": NP_KEY,
        "Content-Type": "application/json"
    }
    payload = {"action": action}
    if body:
        payload.update(body)
    try:
        r = requests.post(NP_API, headers=headers, json=payload, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def get_number(range_id: str) -> dict:
    request_id = secrets.token_hex(8)
    res = np("getnum", {"range": range_id, "requestId": request_id})
    
    if res.get("meta", {}).get("code") == 200 and "data" in res:
        data = res["data"]
        return {
            "success": True,
            "number": data.get("full_number") or ("+" + str(data.get("no_plus_number", ""))),
            "no_plus": data.get("no_plus_number"),
            "operator": data.get("operator"),
            "rid": res.get("rid"),
        }
    return {"success": False, "error": res.get("message") or res.get("error") or str(res)}

def check_otp(number_no_plus: str):
    res = np("inbox")
    for n in res.get("numbers", []):
        if str(n.get("number")) == str(number_no_plus) and n.get("otp"):
            return n.get("otp")
    return None

# ==================== মেনু ====================
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📞 Get Number"), KeyboardButton("🏠 Home"))
    return markup

def get_country_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for name, conf in COUNTRY_CONFIG.items():
        markup.add(KeyboardButton(f"{conf['flag']} {name}"))
    markup.add(KeyboardButton("🏠 Home"))
    return markup

# ==================== হ্যান্ডলার ====================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "✨ *Welcome to Number & OTP Service*\n\nদেশ সিলেক্ট করে নাম্বার নিন।",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "📞 Get Number")
def ask_country(message):
    bot.send_message(message.chat.id, "🌍 *দেশ সিলেক্ট করুন:*", parse_mode="Markdown", reply_markup=get_country_menu())

@bot.message_handler(func=lambda m: any(name in m.text for name in COUNTRY_CONFIG))
def give_number(message):
    selected = next((name for name in COUNTRY_CONFIG if name in message.text), None)
    if not selected:
        return
    
    conf = COUNTRY_CONFIG[selected]
    chat_id = message.chat.id
    
    msg = bot.send_message(chat_id, f"⏳ {conf['flag']} *{selected}* থেকে নাম্বার নেওয়া হচ্ছে...", parse_mode="Markdown")
    
    result = get_number(conf["range"])
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    
    if result["success"]:
        user_sessions[chat_id] = {
            "number": result["no_plus"],
            "full_number": result["number"],
            "country": selected
        }
        markup.add(KeyboardButton("🔄 Check OTP"), KeyboardButton("🔄 Change Number"), KeyboardButton("🏠 Home"))
        
        text = (
            f"{conf['flag']} *{selected}*\n"
            f"📡 `{result.get('operator', 'N/A')}`\n\n"
            f"📱 *Number:* `{result['number']}`\n\n"
            f"⏳ OTP আসার পর *Check OTP* চাপুন।"
        )
    else:
        markup.add(KeyboardButton("🔄 Change Number"), KeyboardButton("🏠 Home"))
        text = f"⚠️ নাম্বার পাওয়া যায়নি\n\n`{result.get('error')}`"
    
    bot.delete_message(chat_id, msg.message_id)
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔄 Check OTP")
def check_otp_handler(message):
    chat_id = message.chat.id
    session = user_sessions.get(chat_id)
    
    if not session:
        bot.send_message(chat_id, "❌ আগে নাম্বার নিন।", reply_markup=get_main_menu())
        return
    
    otp = check_otp(session["number"])
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("🔄 Check OTP"), KeyboardButton("🔄 Change Number"), KeyboardButton("🏠 Home"))
    
    if otp:
        text = f"🔔 *OTP Received!*\n\n📱 `{session['full_number']}`\n📩 *OTP:* `{otp}`"
    else:
        text = f"⏳ এখনো OTP আসেনি।\n\n📱 `{session['full_number']}`\nআবার চেষ্টা করুন।"
    
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔄 Change Number")
def change_number(message):
    bot.send_message(message.chat.id, "🌍 নতুন দেশ সিলেক্ট করুন:", reply_markup=get_country_menu())

@bot.message_handler(func=lambda m: m.text == "🏠 Home")
def home(message):
    bot.send_message(message.chat.id, "🏡 মূল মেনু", reply_markup=get_main_menu())

# ==================== RENDER এর জন্য ====================
app = Flask(__name__)

@app.route("/")
def home_page():
    return "Bot is running!", 200

@app.route("/health")
def health():
    return "OK", 200

def run_bot():
    print("Bot polling started...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=50)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # বট আলাদা থ্রেডে চলবে
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Render যে PORT দেয় সেটায় Flask চলবে
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)