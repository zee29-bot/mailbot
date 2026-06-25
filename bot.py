import sqlite3
import requests
import random
import re
import html
from datetime import datetime
import pytz # 🛠️ ဖုန်းထဲက မြန်မာစံတော်ချိန် အချိန်နှင့် ကိုက်ညီစေရန် ထည့်သွင်းထားသည်
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIGURATION =================
BOT_TOKEN = "8815393066:AAHQsWeDn78kQyCAZoQBcU7p9H42uxpkIwQ"          
LOCK_CODE = "ZEE1682"                
BASE_URL = "https://api.mail.tm"

# ================= DATABASE SETUP =================
conn = sqlite3.connect("mailbot_pro.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("PRAGMA journal_mode=WAL;")
cursor.execute("PRAGMA synchronous=NORMAL;")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    phone_number TEXT,
    is_locked INTEGER DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS client_mails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    email TEXT UNIQUE, 
    password TEXT,
    token TEXT
)
""")
conn.commit()

# ================= DB FUNCTIONS =================
def get_user_status(tg_id):
    try:
        cursor.execute("SELECT phone_number, is_locked FROM users WHERE tg_id=?", (tg_id,))
        return cursor.fetchone()
    except: return None

def create_or_update_user(tg_id, phone=None, is_locked=None):
    try:
        status = get_user_status(tg_id)
        if not status:
            cursor.execute("INSERT INTO users (tg_id, phone_number, is_locked) VALUES (?, ?, ?)", (tg_id, phone, 1 if is_locked is None else is_locked))
        else:
            if phone: cursor.execute("UPDATE users SET phone_number=? WHERE tg_id=?", (phone, tg_id))
            if is_locked is not None: cursor.execute("UPDATE users SET is_locked=? WHERE tg_id=?", (is_locked, tg_id))
        conn.commit()
    except: pass

def add_mail(owner_id, email, password, token):
    try:
        cursor.execute("INSERT INTO client_mails (owner_id, email, password, token) VALUES (?, ?, ?, ?)", (owner_id, email, password, token))
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
    except: return None

def get_my_mails(owner_id):
    try:
        cursor.execute("SELECT id, email FROM client_mails WHERE owner_id=?", (owner_id,))
        return cursor.fetchall()
    except: return []

def get_mail_details(mail_id, owner_id):
    try:
        cursor.execute("SELECT email, token FROM client_mails WHERE id=? AND owner_id=?", (mail_id, owner_id))
        return cursor.fetchone()
    except: return None

def delete_my_mail(mail_id, owner_id):
    try:
        cursor.execute("DELETE FROM client_mails WHERE id=? AND owner_id=?", (mail_id, owner_id))
        conn.commit()
    except: pass

def change_mail_owner_by_email(email, current_owner, new_owner):
    try:
        cursor.execute("SELECT id FROM client_mails WHERE email=? AND owner_id=?", (email, current_owner))
        if cursor.fetchone():
            cursor.execute("INSERT OR IGNORE INTO users (tg_id, phone_number, is_locked) VALUES (?, NULL, 0)", (new_owner,))
            cursor.execute("UPDATE client_mails SET owner_id=? WHERE email=?", (new_owner, email))
            conn.commit()
            return True
        return False
    except:
        return False

# ================= MAIL API FUNCTIONS =================
def create_mail_api(password, custom_name=None):
    try:
        domain_data = requests.get(f"{BASE_URL}/domains", timeout=10).json()
        domain = domain_data["hydra:member"][0]["domain"]
        
        if custom_name:
            clean_name = re.sub(r'[^a-zA-Z0-9._]', '', custom_name).lower()
            if not clean_name: return None
            email = f"{clean_name}@{domain}"
        else:
            email = f"user{random.randint(1000,999999)}@{domain}"
        
        acc = requests.post(f"{BASE_URL}/accounts", json={"address": email, "password": password}, timeout=10)
        if acc.status_code != 201: return None
        
        token_data = requests.post(f"{BASE_URL}/token", json={"address": email, "password": password}, timeout=10).json()
        return email, token_data.get("token")
    except: return None

def login_mail_api(email, password):
    try:
        token_data = requests.post(f"{BASE_URL}/token", json={"address": email, "password": password}, timeout=10).json()
        if "token" in token_data:
            return token_data["token"]
        return None
    except: return None

def check_inbox_api(token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{BASE_URL}/messages", headers=headers, timeout=10).json()
        return res.get("hydra:member", [])
    except: 
        return []

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    status = get_user_status(uid)
    
    if not status or status[1] == 1:
        create_or_update_user(uid, is_locked=1)
        await update.message.reply_text("<b>Welcome to Fake Mail Bot</b>\n\nဤ Bot အား သုံးစွဲရန် လျှို့ဝှက်ချက် Lock Code ကို အရင်ရိုက်ထည့်ပေးပါရန်။")
        return

    if not status[0]:
        contact_btn = KeyboardButton(text="ဖုန်းနံပါတ်ဖြင့် Verify လုပ်မည်", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_btn]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Bot အသုံးပြုရန် သင့်ရဲ့ Telegram ဖုန်းနံပါတ်အား Share ပေးရန် လိုအပ်ပါတယ်ခင်ဗျာ။", reply_markup=reply_markup)
        return

    await update.message.reply_text(
        f"<b>Fake Mail Bot Pro</b>\n\n"
        "<b>အသုံးပြုနိုင်သော Command များ -</b>\n"
        "➡️ <code>/generate သင့်Password</code> - Random မေးလ်ဆောက်မည်။\n"
        "➡️ <code>/set နာမည် သင့်Password</code> - စိတ်ကြိုက်နာမည်ဖြင့် ဆောက်မည်။\n"
        "➡️ <code>/login မေးလ်လိပ်စာ သင့်Password</code> - မေးလ်ဟောင်းအား ဝင်ရောက်မည်။\n"
        "➡️ /id - မိမိမေးလ်စာရင်းနှင့် OTP စစ်ဆေးရန်။\n"
        "➡️ /help - အသုံးပြုနည်းလမ်းညွှန် ဖတ်ရန်။",
        parse_mode="HTML"
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.contact: return
    contact = update.message.contact
    uid = update.effective_user.id
    
    if contact.user_id != uid:
        await update.message.reply_text("သင့်ကိုယ်ပိုင် ဖုန်းနံပါတ်အစစ်အမှန်ဖြင့်သာ ပြုလုပ်ပေးပါ။")
        return
        
    create_or_update_user(uid, phone=contact.phone_number)
    await update.message.reply_text("ဖုန်းနံပါတ်စစ်ဆေးခြင်း အောင်မြင်သွားပါပြီ။ /start ကို နှိပ်ပြီး စတင်အသုံးပြုပါ။", reply_markup=ReplyKeyboardRemove())

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    status = get_user_status(uid)
    if not status or status[1] == 1 or not status[0]: return

    if not context.args:
        await update.message.reply_text("သုံးနည်း - <code>/generate သင့်Password</code> ဟု ရိုက်ပါ။", parse_mode="HTML")
        return

    user_password = context.args[0]
    await update.message.reply_text("မေးလ်အသစ် ဆောက်နေပါတယ်...")
    result = create_mail_api(password=user_password)
    
    if not result:
        await update.message.reply_text("မေးလ်ဆောက်၍ မရပါ။ ခဏနေမှ ပြန်ကြိုးစားပါ။")
        return
        
    email, token = result
    add_mail(uid, email, user_password, token)
    safe_email = html.escape(email)
    safe_pass = html.escape(user_password)
    await update.message.reply_text(f"မေးလ်အသစ် ရပါပြီ -\n📧 Mail: <code>{safe_email}</code>\n🔑 Pass: <code>{safe_pass}</code>", parse_mode="HTML")

async def set_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    status = get_user_status(uid)
    if not status or status[1] == 1 or not status[0]: return
    
    if len(context.args) < 2:
        await update.message.reply_text("သုံးနည်း - <code>/set နာမည် သင့်Password</code> ဟု ရိုက်ပါ။", parse_mode="HTML")
        return
        
    custom_name = context.args[0]
    user_password = context.args[1]
    
    await update.message.reply_text("စိတ်ကြိုက်မေးလ် ဆောက်နေပါတယ်...")
    result = create_mail_api(password=user_password, custom_name=custom_name)
    
    if not result:
        await update.message.reply_text("ဤနာမည်သည် မရနိုင်ပါ။ အခြားနာမည်ပြောင်းပါ။")
        return
        
    email, token = result
    add_mail(uid, email, user_password, token)
    safe_email = html.escape(email)
    safe_pass = html.escape(user_password)
    await update.message.reply_text(f"စိတ်ကြိုက်မေးလ် ရပါပြီ -\n📧 Mail: <code>{safe_email}</code>\n🔑 Pass: <code>{safe_pass}</code>", parse_mode="HTML")

async def login_mail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    status = get_user_status(uid)
    if not status or status[1] == 1 or not status[0]: return

    if len(context.args) < 2:
        await update.message.reply_text("သုံးနည်း - <code>/login မေးလ်လိပ်စာ သင့်Password</code> ဟု ရိုက်ပါ။", parse_mode="HTML")
        return

    input_email = context.args[0].strip().lower()
    input_password = context.args[1].strip()

    existing_owner = check_mail_exist(input_email)
    if existing_owner:
        if existing_owner[0] == uid:
            await update.message.reply_text("ဤမေးလ်သည် သင့် Bot ထဲတွင် ထည့်သွင်းထားပြီးသား ဖြစ်ပါသည်။")
        else:
            await update.message.reply_text("ဝင်ရောက်၍မရပါ၊ ဤမေးလ်အား လက်ရှိတွင် အခြားအသုံးပြုသူတစ်ဦးက အသုံးပြုနေပါသည်။")
        return

    await update.message.reply_text("မေးလ်အကောင့်ကို စစ်ဆေးပြီး ပြန်လည်ချိတ်ဆက်နေပါတယ်...")
    token = login_mail_api(input_email, input_password)

    if token:
        if add_mail(uid, input_email, input_password, token):
            safe_email = html.escape(input_email)
            await update.message.reply_text(f"မေးလ်ဝင်ရောက်မှု အောင်မြင်ပါသည်။\n📧 Mail: <code>{safe_email}</code>", parse_mode="HTML")
        else:
            await update.message.reply_text("ဤမေးလ်အား အခြားသူတစ်ဦးက သုံးစွဲနေဆဲဖြစ်ပါသည်။")
    else:
        await update.message.reply_text("မေးလ်လိပ်စာ သို့မဟုတ် Password မှားယွင်းနေပါသည်။")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    help_text = (
        "<b>Fake Mail Bot Pro - အသုံးပြုနည်း</b>\n\n"
        "<b>မေးလ်ဆောက်ခြင်း</b>\n"
        "➡️ <code>/generate သင့်Password</code>\n"
        "➡️ <code>/set နာမည် သင့်Password</code>\n\n"
        "<b>မေးလ်လော့ဂ်အင်ဝင်ခြင်း</b>\n"
        "➡️ <code>/login မေးလ်လိပ်စာ သင့်Password</code>\n\n"
        "<b>မေးလ်လွှဲပြောင်းခြင်း</b>\n"
        "➡️ <code>/transfer_မေးလ်လိပ်စာ တဖက်လူID</code>\n"
        "*(ဥပမာ- /transfer_user123@domain.com 5238487314)*\n\n"
        "<b>OTP စစ်ခြင်း</b>\n"
        "➡️ /id ကိုရိုက်၍ ကျလာသော ขလုတ်ကို နှိပ်ပါ။"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def show_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    status = get_user_status(uid)
    if not status or status[1] == 1 or not status[0]: return
    
    mails = get_my_mails(uid)
    if not mails:
        await update.message.reply_text("သင့်ထံတွင် လက်ရှိ ဆောက်ထားသော မေးလ်မရှိသေးပါ။")
        return
        
    await update.message.reply_text("<b>သင့်ကိုယ်ပိုင် မေးလ်စာရင်း -</b>", parse_mode="HTML")
    
    for mail_id, email in mails:
        safe_email = html.escape(email)
        text = f"📧 <b>Mail:</b> <code>{safe_email}</code>"
        
        keyboard = [
            [
                InlineKeyboardButton("📥 စစ်မည် (OTP)", callback_data=f"chk_{mail_id}"),
                InlineKeyboardButton("🗑️ ထွက်မည်/ဖျက်မည်", callback_data=f"del_{mail_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

# 🛠️ [UPDATED WITH TIMEZONE] မြန်မာစံတော်ချိန် (ဖုန်းအချိန်) စင့်ခ်လုပ်ထားသော Inbox စစ်ဆေးစနစ်
async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data
    
    await query.answer()
    
    if data.startswith("chk_"):
        mail_id = int(data.split("_")[1])
        mail_info = get_mail_details(mail_id, uid)
        if not mail_info:
            await query.message.reply_text("ဤမေးလ်သည် သင်ပိုင်ဆိုင်သော မေးလ်မဟုတ်တော့ပါ။")
            return
            
        email, token = mail_info
        messages = check_inbox_api(token)
        safe_email = html.escape(email)
        
        if not messages:
            await query.message.reply_text(f"<code>{safe_email}</code> တွင် မည်သည့်စာ/OTP မျှ မရှိသေးပါ။", parse_mode="HTML")
            return
            
        inbox_text = f"<code>{safe_email}</code> သို့ ဝင်လာသော စာများ -\n\n"
        for msg in messages[:5]:
            from_addr = html.escape(msg.get('from', {}).get('address', 'Unknown'))
            subject = html.escape(msg.get('subject', 'No Subject'))
            intro = html.escape(msg.get('intro', 'No Content'))
            
            created_at = msg.get('createdAt', '')
            formatted_time = "Unknown Time"
            if created_at:
                try:
                    # API မှလာသော UTC အချိန်စာသားကို ဖတ်ယူခြင်း
                    clean_time_str = created_at.split('.')[0].replace('T', ' ')
                    utc_dt = datetime.strptime(clean_time_str, '%Y-%m-%d %H:%M:%S')
                    
                    # ကမ္ဘာ့စံတော်ချိန် (UTC) မှ အစ်ကို့ဖုန်းထဲက မြန်မာစံတော်ချိန် (Asia/Yangon) သို့ အလိုအလျောက် ပြောင်းခြင်း
                    utc_zone = pytz.timezone('UTC')
                    mm_zone = pytz.timezone('Asia/Yangon')
                    
                    utc_dt = utc_zone.localize(utc_dt)
                    mm_dt = utc_dt.astimezone(mm_zone)
                    
                    # ဖတ်ရလွယ်သော မြန်မာစံတော်ချိန် ပုံစံထုတ်ခြင်း
                    formatted_time = mm_dt.strftime('%d-%b-%Y (%I:%M %p)')
                except:
                    formatted_time = str(created_at)

            inbox_text += f"👤 <b>From:</b> {from_addr}\n"
            inbox_text += f"📅 <b>Time:</b> <code>{formatted_time}</code>\n"
            inbox_text += f"📝 <b>Subject:</b> {subject}\n"
            inbox_text += f"💬 <b>Content:</b> {intro}\n────────────────────\n"
            
        await query.message.reply_text(inbox_text, parse_mode="HTML")
        
    elif data.startswith("del_"):
        mail_id = int(data.split("_")[1])
        delete_my_mail(mail_id, uid)
        await query.edit_message_text("🗑️ ဤမေးလ်အား Bot စာရင်းထဲမှ ဖယ်ထုတ်ပြီးပါပြီ။")

async def dynamic_and_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    uid = update.effective_user.id
    text = update.message.text.strip()
    status = get_user_status(uid)

    if status and status[1] == 1:
        if text == LOCK_CODE:
            create_or_update_user(uid, is_locked=0)
            await update.message.reply_text("Lock Code မှန်ကန်ပါသည်။")
            await start(update, context)
        else:
            await update.message.reply_text("Lock Code မှားယွင်းနေပါသည်။ ထပ်မံကြိုးစားပါ။")
        return

    if not status or status[0] is None: return

    if text.startswith("/transfer_") or text.startswith("/transfer"):
        try:
            clean_text = text.replace("/transfer_", "").replace("/transfer", "").strip()
            parts = clean_text.split()
            
            if len(parts) < 2:
                await update.message.reply_text("⚠️ သုံးနည်း - <code>/transfer_မေးလ်လိပ်စာ တဖက်လူID</code>", parse_mode="HTML")
                return
                
            target_email = parts[0].strip().lower()
            new_owner = int(parts[1].strip())
            
            if change_mail_owner_by_email(target_email, uid, new_owner):
                safe_mail = html.escape(target_email)
                await update.message.reply_text(f"မေးလ် <code>{safe_mail}</code> အား User ID (<code>{new_owner}</code>) သို့ လွှဲပြောင်းပေးလိုက်ပါပြီ။", parse_mode="HTML")
            else:
                await update.message.reply_text("လွှဲပြောင်းခြင်း မအောင်မြင်ပါ။ အဆိုပါမေးလ်သည် သင့်ထံတွင် ရှိမနေပါ သို့မဟုတ် မှားယွင်းနေပါသည်။")
        except:
            await update.message.reply_text("⚠️ သုံးနည်း - <code>/transfer_မေးလ်လိပ်စာ တဖက်လူID</code>", parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("set", set_custom))
    app.add_handler(CommandHandler("login", login_mail))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", show_ids))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(CallbackQueryHandler(button_click_handler))
    app.add_handler(MessageHandler(filters.TEXT, dynamic_and_text_messages))
    print("Timezone-Synced Mail Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
