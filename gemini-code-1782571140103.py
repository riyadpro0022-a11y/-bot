import os
import requests
import time
import random
import logging
import warnings
from datetime import datetime, timedelta, timezone
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading

warnings.filterwarnings("ignore")
telebot.logger.setLevel(logging.CRITICAL)

BOT_TOKEN = "8900431307:AAEe16r5ZjKjC61Bc5dKYNHmDtb_YoUzk8Y"
CHAT_ID = "-1002484359858"
ADMIN_ID = 6745297891

bot = telebot.TeleBot(BOT_TOKEN)

session_state = "IDLE"
session_type = None  
predictions_given = 0
target_predictions = 20
temp_target = 0
current_step = 1
pH = [] 
pred_sent_for = set()
result_sent_for = set()
pCa = {}
history_log = [] 
alert_sent_times = set()
history_wait_start = 0
post_sticker_sent = False

# অ্যাডমিন প্যানেল আপডেট করার জন্য গ্লোবাল ভেরিয়েবল
admin_chat_id = None
admin_msg_id = None

schedules = {
    "10:10": {"msg_time": "10:00", "sticker_time": "10:05", "target": 20},
    "13:10": {"msg_time": "13:00", "sticker_time": "13:05", "target": 20},
    "21:10": {"msg_time": "21:00", "sticker_time": "21:05", "target": 20}
}

temp_add_data = {}

def get_local_time():
    bd_tz = timezone(timedelta(hours=6))
    return datetime.now(bd_tz)

def opp(size):
    return "Small" if size == "Big" else "Big"

def fq(arr):
    b = sum(1 for x in arr if x == "Big")
    l = len(arr)
    return {'b': b, 's': l - b, 'd': abs(2 * b - l), 'ratio': b / l if l > 0 else 0}

def avg(arr):
    return sum(arr) / len(arr) if arr else 4.5

# =========================================================
# 22.html থেকে নেওয়া নতুন PREDICTION LOGIC 
# =========================================================
def predict(hist, period):
    global pCa
    if period in pCa: return pCa[period]

    # HTML ফাইলের লজিক অনুযায়ী: "Generate only BIG or SMALL prediction" (Randomly)
    predictions_list = ["Big", "Small"]
    pred_text = random.choice(predictions_list)
    
    # বটের অন্য ফিচারের জন্য একটি ডিফল্ট কনফিডেন্স ভ্যালু সেট করা হলো (কারণ HTML এ এটি ছিল না)
    c = random.randint(70, 99)
    
    res = {"text": pred_text, "conf": c}
    
    pCa[period] = res
    if len(pCa) > 100: pCa.pop(next(iter(pCa)))
    
    return res
# =========================================================

def send_message(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=data, timeout=5)
    except: pass

def send_sticker(sticker_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendSticker"
    data = {"chat_id": CHAT_ID, "sticker": sticker_id}
    try: requests.post(url, json=data, timeout=5)
    except: pass

def trigger_summary_report():
    global history_log
    if not history_log: return

    win_count = sum(1 for item in history_log if item['status'] == "Win")
    loss_count = len(history_log) - win_count
    
    msg = f"📊 <b>SESSION SUMMARY ({len(history_log)} VIP SIGNALS)</b> 📊\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n\n"
    for item in history_log:
        icon = "✅" if item['status'] == "Win" else "❌"
        msg += f"🔹 <b>{item['period']}</b>  ➤  {item['status']} {icon}\n"
        
    msg += f"\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n"
    msg += f"🏆 <b>TOTAL WINS  : {win_count}</b>\n"
    msg += f"💔 <b>TOTAL LOSS  : {loss_count}</b>\n"
    msg += "<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n<b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗</b>"

    send_message(msg)
    history_log = []

def trigger_prediction(period, prediction):
    if period in pred_sent_for: return
    pred_sent_for.add(period)

    sec = get_local_time().second
    rem = (30 - sec) if sec < 30 else (60 - sec)
    
    is_big = prediction.upper() == "BIG"
    title = "🔴🔥 <b>BIG SIGNAL</b> 🔥🔴" if is_big else "🟢🌿 <b>SMALL SIGNAL</b> 🌿🟢"
    action_text = "<b>BET BIG</b> 🔴" if is_big else "<b>BET SMALL</b> 🟢"
    
    msg = f"{title}\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n<b>💎 Period   ➤  {period}</b>\n<b>🎯 Action   ➤  {action_text}</b>\n<b>⚡ Time     ➤  {rem}s</b>\n<b>🔥 Step     ➤  {current_step} STEP</b>\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n<b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗</b>"
    
    big_sticker = "CAACAgUAAxkBAAERMUtqAUrDKj4pj-_U2YrekuPYVg11YwACxxoAAo_L0FX9CmmfkRimPDsE"
    small_sticker = "CAACAgUAAxkBAAERMU1qAUrG1zttGD8RZhNPxjR7z39LIQACvxoAAmTK0VWjRAfZBmvyiTsE"
    sticker_id = big_sticker if is_big else small_sticker
    
    send_message(msg)
    send_sticker(sticker_id)

def trigger_result(period, status):
    global history_log, session_state, history_wait_start, post_sticker_sent
    if period in result_sent_for: return
    result_sent_for.add(period)
    
    history_log.append({"period": period, "status": status})
    
    is_win = (status == "Win")
    title_text = "🎉🏆 <b>SUPER WIN</b> 🏆🎉" if is_win else "❌💔 <b>MISSED</b> 💔❌"
    result_text = "<b>WIN ✅</b>" if is_win else "<b>LOSS ❌</b>"
    
    msg = f"{title_text}\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n<b>💎 Period   ➤  {period}</b>\n<b>📊 Result   ➤  {result_text}</b>\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n<b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗</b>"
    
    win_stickers = [
        "CAACAgUAAxkBAAERMU9qAUtYM1qTKsi7fcmU9o-lsF7P_wAC9BkAAkO4uFSiMGTGRLvivDsE", 
        "CAACAgUAAxkBAAIB1GogWWhRZC_67uwtaH_Es9rtW8-TAAKpGwAC3C5hVa7e4m7w_QybOwQ", 
        "CAACAgUAAxkBAAIB1mogWd8Swolw5aPX0I-Mb6fLm5hqAAJhGAAC5I3ZVQnlnyqqhaKyOwQ", 
        "CAACAgUAAxkBAAIB2GogWeJhq4M6Mti5Jt3IQb101KxxAALJJAACkDvZVb9TW1jT-_iMOwQ", 
        "CAACAgUAAxkBAAIB2mogWeZm9cQNuhaGHCIPj6borpMNAAKXKQAC87rZVYEYTUyAurCzOwQ", 
        "CAACAgUAAxkBAAIB3GogWemoFxEe2bX_5UUZFmBj4tb2AALgGAACYhXYVactg5xcFMmcOwQ"  
    ]
    loss_sticker = "CAACAgUAAxkBAAERMVFqAUwpwT4Xwyfnv5Mg_3CB_88IzQACrxsAAjrxkFZlglZhqNc4mzsE"
    
    send_message(msg)
    
    if is_win:
        selected_stickers = random.sample(win_stickers, 3)
        for st_id in selected_stickers:
            send_sticker(st_id)
            time.sleep(0.3) 
    else:
        send_sticker(loss_sticker)
    
    if predictions_given >= target_predictions and is_win:
        session_state = "WAITING_HISTORY"
        history_wait_start = time.time()
        post_sticker_sent = False 

def fetch_and_predict():
    global current_step, pH, predictions_given
    url = f"https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json?r={int(time.time()*1000)}"
    
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        if not data or 'data' not in data or 'list' not in data['data']: 
            return
        
        items = data['data']['list'][:20]
        hist = []
        for item in items:
            period_num = item.get('issueNumber') or item.get('IssueNumber')
            num = int(item.get('number') or item.get('Number') or item.get('openNumber'))
            size = "Big" if num >= 5 else "Small"
            hist.append({"period": period_num, "number": num, "size": size})
            
        if not hist: return
        next_p = str(int(hist[0]['period']) + 1)
        result_found = False
        
        for p in pH:
            match = next((h for h in hist if h['period'] == p['period']), None)
            if match and p['status'] == "Waiting":
                p['actual'] = match['size']
                if p['prediction'].lower() == p['actual'].lower():
                    p['status'] = "Win"
                    current_step = 1
                else:
                    p['status'] = "Loss"
                    current_step += 1
                trigger_result(p['period'], p['status'])
                result_found = True
                
        if session_state == "RUNNING" and next_p not in pred_sent_for and not any(p['period'] == next_p for p in pH):
            predictions_given += 1
            pd = predict(hist, next_p)
            pred_text = pd['text']
            pH.insert(0, {"period": next_p, "prediction": pred_text, "status": "Waiting"})
            
            if result_found:
                time.sleep(5)
                
            trigger_prediction(next_p, pred_text)

    except Exception:
        pass

def get_bengali_time_str(time_str):
    t = datetime.strptime(time_str, "%H:%M")
    h = t.hour
    if h < 12: period = "সকাল"
    elif h < 15: period = "দুপুর"
    elif h < 18: period = "বিকাল"
    elif h < 20: period = "সন্ধ্যা"
    else: period = "রাত"
    h_12 = h if h <= 12 else h - 12
    if h_12 == 0: h_12 = 12
    eng_to_bn = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')
    return f"{period} {str(h_12).translate(eng_to_bn)}:{t.strftime('%M').translate(eng_to_bn)}"

def admin_keyboard():
    markup = InlineKeyboardMarkup()
    if session_state != "IDLE" and session_type == "INSTANT":
        markup.add(InlineKeyboardButton("🛑 Stop Prediction", callback_data="stop_pred"))
    else:
        markup.add(InlineKeyboardButton("🚀 Instant Prediction", callback_data="inst_pred"))
        
    markup.add(InlineKeyboardButton("➕ Add Schedule", callback_data="add_sch"),
               InlineKeyboardButton("➖ Remove Schedule", callback_data="rem_sch"))
    markup.add(InlineKeyboardButton("📅 View Schedules", callback_data="view_sch"))
    return markup

def confirm_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Yes", callback_data="inst_yes"),
               InlineKeyboardButton("❌ No", callback_data="inst_no"))
    return markup

def back_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    return markup

def remove_keyboard():
    markup = InlineKeyboardMarkup()
    for st in sorted(schedules.keys()):
        markup.add(InlineKeyboardButton(f"❌ Remove {st}", callback_data=f"del_{st}"))
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    global admin_chat_id, admin_msg_id
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>\nManage your bot schedules below:", parse_mode="HTML", reply_markup=admin_keyboard())
    admin_chat_id = msg.chat.id
    admin_msg_id = msg.message_id

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global session_state, session_type, predictions_given, current_step, pH, history_log, target_predictions, admin_chat_id, admin_msg_id

    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ You are not authorized!")
        return
        
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    admin_chat_id = chat_id
    admin_msg_id = msg_id

    if call.data == "main_menu":
        bot.answer_callback_query(call.id)
        bot.clear_step_handler_by_chat_id(chat_id)
        bot.edit_message_text("🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>\nManage your bot schedules below:",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

    elif call.data == "inst_pred":
        if session_state != "IDLE":
            bot.answer_callback_query(call.id, "⚠️ A session is already running!", show_alert=True)
            bot.edit_message_text("🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>\nManage your bot schedules below:",
                                  chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())
            return
        bot.answer_callback_query(call.id)
        bot.edit_message_text("🔢 <b>আপনি কতগুলো প্রেডিকশন চান?</b> (যেমন: 10):",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=back_keyboard())
        bot.register_next_step_handler(call.message, process_inst_count, msg_id)

    elif call.data == "stop_pred":
        if session_state == "IDLE" or session_type != "INSTANT":
            bot.answer_callback_query(call.id, "⚠️ No instant session is running!", show_alert=True)
            bot.edit_message_text("🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>\nManage your bot schedules below:",
                                  chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())
            return
            
        target_predictions = 0
        bot.answer_callback_query(call.id, "✅ Stopping at next win...", show_alert=True)
        bot.edit_message_text("🛑 <b>Stop Request Accepted!</b>\nবর্তমান সিগন্যাল Win হওয়ার সাথেই বট হিস্টোরি পাঠিয়ে অফ হয়ে যাবে।\n\n🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

    elif call.data == "inst_yes":
        bot.answer_callback_query(call.id)
        target_predictions = temp_target
        session_state = "RUNNING"
        session_type = "INSTANT"
        predictions_given = 0
        current_step = 1
        pH = []
        history_log = []
        bot.edit_message_text(f"🚀 <b>Instant Prediction Started!</b> ({target_predictions} Signals)\n\n🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

    elif call.data == "inst_no":
        bot.answer_callback_query(call.id)
        bot.edit_message_text("🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>\nManage your bot schedules below:",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

    elif call.data == "view_sch":
        bot.answer_callback_query(call.id)
        if not schedules:
            sch_text = "No schedules set."
        else:
            sch_text = ""
            for st in sorted(schedules.keys()):
                d = schedules[st]
                count = d.get('target', 20)
                sch_text += f"🕒 <b>{st}</b> <i>(Msg: {d['msg_time']} | Sticker: {d['sticker_time']} | Count: {count})</i>\n"
        bot.edit_message_text(f"<b>Current Schedules:</b>\n\n{sch_text}",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=back_keyboard())

    elif call.data == "rem_sch":
        if not schedules:
            bot.answer_callback_query(call.id, "⚠️ No schedules to remove!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.edit_message_text("🗑️ <b>Select a schedule to remove:</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=remove_keyboard())

    elif call.data.startswith("del_"):
        time_to_del = call.data.split("_")[1]
        if time_to_del in schedules:
            del schedules[time_to_del]
            bot.answer_callback_query(call.id, f"✅ Schedule {time_to_del} removed!", show_alert=True)
        
        if schedules:
            bot.edit_message_text("🗑️ <b>Select a schedule to remove:</b>",
                                  chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=remove_keyboard())
        else:
            bot.edit_message_text("🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>\n\n<i>(All schedules removed)</i>",
                                  chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

    elif call.data == "add_sch":
        bot.answer_callback_query(call.id)
        bot.edit_message_text("1️⃣ <b>Attention Message যাওয়ার সময় দিন</b> (যেমন 14:00):",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=back_keyboard())
        bot.register_next_step_handler(call.message, process_add_msg, msg_id)

def process_inst_count(message, msg_id):
    global temp_target
    if message.from_user.id != ADMIN_ID: return
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    try:
        val = int(message.text.strip())
        if val <= 0: raise ValueError
        temp_target = val
        bot.edit_message_text(f"⚠️ <b>আপনি কি {val} টি প্রেডিকশন চালু করতে চান?</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=confirm_keyboard())
    except ValueError:
        bot.edit_message_text("❌ Invalid number!\n\n🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

def process_add_msg(message, msg_id):
    if message.from_user.id != ADMIN_ID: return
    chat_id = message.chat.id
    time_str = message.text.strip()
    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    try:
        datetime.strptime(time_str, "%H:%M")
        temp_add_data[chat_id] = {'msg': time_str}
        bot.edit_message_text("2️⃣ <b>Sticker যাওয়ার সময় দিন</b> (যেমন 14:05):",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=back_keyboard())
        bot.register_next_step_handler(message, process_add_stk, msg_id)
    except ValueError:
        bot.edit_message_text("❌ Invalid format! Use HH:MM format.\n\n🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

def process_add_stk(message, msg_id):
    if message.from_user.id != ADMIN_ID: return
    chat_id = message.chat.id
    time_str = message.text.strip()
    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    try:
        datetime.strptime(time_str, "%H:%M")
        temp_add_data[chat_id]['stk'] = time_str
        bot.edit_message_text("3️⃣ <b>Prediction শুরু হওয়ার সময় দিন</b> (যেমন 14:10):",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=back_keyboard())
        bot.register_next_step_handler(message, process_add_start, msg_id)
    except ValueError:
        bot.edit_message_text("❌ Invalid format! Use HH:MM format.\n\n🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

def process_add_start(message, msg_id):
    if message.from_user.id != ADMIN_ID: return
    chat_id = message.chat.id
    time_str = message.text.strip()
    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    try:
        datetime.strptime(time_str, "%H:%M")
        temp_add_data[chat_id]['start'] = time_str
        bot.edit_message_text("4️⃣ <b>কতগুলো প্রেডিকশন দিতে চান?</b> (যেমন: 20):",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=back_keyboard())
        bot.register_next_step_handler(message, process_add_count, msg_id)
    except ValueError:
        bot.edit_message_text("❌ Invalid format! Use HH:MM format.\n\n🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

def process_add_count(message, msg_id):
    if message.from_user.id != ADMIN_ID: return
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    try:
        val = int(message.text.strip())
        if val <= 0: raise ValueError
        
        st = temp_add_data[chat_id]['start']
        msg_time = temp_add_data[chat_id]['msg']
        stk_time = temp_add_data[chat_id]['stk']
        
        schedules[st] = {
            'msg_time': msg_time,
            'sticker_time': stk_time,
            'target': val
        }
        
        text = f"✅ Schedule Added Successfully!\n\n🕒 <b>Prediction:</b> {st}\n💬 <b>Message:</b> {msg_time}\n🎨 <b>Sticker:</b> {stk_time}\n🎯 <b>Signals:</b> {val}\n\n🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>"
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())
    except ValueError:
        bot.edit_message_text("❌ Invalid number!\n\n🤖 <b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Admin Panel</b>",
                              chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=admin_keyboard())

def auto_scheduler():
    global session_state, predictions_given, current_step, pH, history_log, history_wait_start, post_sticker_sent, target_predictions, session_type, admin_chat_id, admin_msg_id

    print("🚀 𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗ Pydroid 3 Auto-Schedule Bot Started!")
    while True:
        now = get_local_time()
        hm = now.strftime("%H:%M")
        date_str = now.strftime("%Y-%m-%d")

        if hm in ["06:00", "23:00"]:
            daily_alert_key = f"{date_str}-{hm}-daily_sticker"
            if daily_alert_key not in alert_sent_times:
                if hm == "06:00":
                    sticker_id = "CAACAgUAAxkBAAIB5Gog6PXVTHUOXQHnwwNkxIGh3INLAALOHAACon0gVOuhk75diDnXOwQ"
                    msg = f"🌅 <b>GOOD MORNING VIPs</b> 🌅\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n\n<b>নতুন একটি দিন, কালার ট্রেডিংয়ে নতুন প্রোফিটের সম্ভাবনা! 💸\nআজকেও আমাদের AI Hack দিয়ে মার্কেট থেকে ভালো কিছু নেওয়ার প্রস্তুতি নিন। সবাই ফান্ড রেডি রাখুন, আজকে আমরা বিগ প্রফিট করবো ইনশাআল্লাহ! 🚀</b>\n\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n<b>𝐎𝐰𝐧𝐞𝐫 𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗</b>"
                    send_sticker(sticker_id)
                    time.sleep(0.5)
                    send_message(msg)
                else: 
                    sticker_id = "CAACAgUAAxkBAAIB5mog6PrY1tlVYVX-ssTZFZzkZJVPAAIHHgACpLghVPJoR9DdQofAOwQ"
                    msg = f"🌙 <b>GOOD NIGHT VIPs</b> 🌙\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n\n<b>আজকের কালার ট্রেডিং সেশনগুলো থেকে আমরা দারুণ প্রোফিট বের করেছি! 🏆\nযারা সাথে ছিলেন সবাইকে অভিনন্দন। এখন ভালোভাবে রেস্ট নিন, আগামীকাল আবার নতুন টার্গেট নিয়ে মার্কেটে নামবো। শান্তিতে ঘুমান! 💤</b>\n\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n<b>𝐎𝐰𝐧𝐞𝐫 𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗</b>"
                    send_message(msg)
                    time.sleep(0.5)
                    send_sticker(sticker_id)
                alert_sent_times.add(daily_alert_key)

        for st, data in schedules.items():
            msg_t = data['msg_time']
            if hm == msg_t:
                alert_key = f"{date_str}-{hm}-msg_alert"
                if alert_key not in alert_sent_times:
                    session_time_bd = get_bengali_time_str(st)
                    msg = f"🔔 <b>ATTENTION</b> 🔔\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n\n<b>{session_time_bd} এ ai hack দিয়ে signal দেওয়া হবে।\nসবাই deposit করে ready থাকেন।</b>\n\n<b>▱▱▱▱▱▱▱▱▱▱▱▱▱▱</b>\n<b>𝐀𝐌𝐆 𝐤𝐢𝐥𝐥𝐞𝐫 ✗</b>"
                    send_message(msg)
                    alert_sent_times.add(alert_key)
            
            stk_t = data['sticker_time']
            if hm == stk_t:
                alert_key = f"{date_str}-{hm}-stk_alert"
                if alert_key not in alert_sent_times:
                    sticker_id = "CAACAgUAAxkBAAEROFxqBxnprFSqwGVuagKwE9fPcx77UQAC6h0AAopBYFXrdlni3cksjjsE"
                    send_sticker(sticker_id)
                    alert_sent_times.add(alert_key)

        if hm in schedules and session_state == "IDLE":
            target_predictions = schedules[hm].get('target', 20)  # ডাইনামিক প্রেডিকশন টার্গেট এখানে সেট হবে
            session_state = "RUNNING"
            session_type = "SCHEDULED"
            predictions_given = 0
            current_step = 1
            pH = []
            history_log = []

        if session_state == "RUNNING":
            fetch_and_predict()

        if session_state == "WAITING_HISTORY":
            time_passed = time.time() - history_wait_start
            
            if not post_sticker_sent and time_passed >= 10:
                sticker_id = "CAACAgUAAxkBAAEROF5qBxnsCHyYjGX0q5W9EFmLJMSD5gACiBkAAv0QaVVzr_WV_kpeSzsE"
                send_sticker(sticker_id)
                post_sticker_sent = True
                
            if time_passed >= 15:
                trigger_summary_report()
                session_state = "IDLE"
                session_type = None
                
                # হিস্টোরি পাঠানোর সাথে সাথেই বাটন চেঞ্জ করে Instant Prediction করে দেওয়া হবে
                if admin_chat_id and admin_msg_id:
                    try:
                        bot.edit_message_reply_markup(chat_id=admin_chat_id, message_id=admin_msg_id, reply_markup=admin_keyboard())
                    except Exception:
                        pass

        time.sleep(3) 

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    threading.Thread(target=auto_scheduler, daemon=True).start()
    bot.infinity_polling()