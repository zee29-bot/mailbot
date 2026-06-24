import sqlite3
import requests
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8815393066:AAHQsWeDn78kQyCAZoQBcU7p9H42uxpkIwQ
"
BASE_URL = "https://api.mail.tm"

# ================= DATABASE =================
conn = sqlite3.connect("mailbot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS owner (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS mails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    email TEXT,
    password TEXT,
    token TEXT
)
""")

conn.commit()


# ================= DB FUNCTIONS =================
def get_owner():
    cursor.execute("SELECT owner_id FROM owner WHERE id=1")
    row = cursor.fetchone()
    return row[0] if row else None


def set_owner(owner_id):
    cursor.execute("INSERT OR REPLACE INTO owner (id, owner_id) VALUES (1, ?)", (owner_id,))
    conn.commit()


def clear_owner():
    cursor.execute("DELETE FROM owner WHERE id=1")
    conn.commit()


def add_mail(owner_id, email, password, token):
    cursor.execute(
        "INSERT INTO mails (owner_id, email, password, token) VALUES (?, ?, ?, ?)",
        (owner_id, email, password, token)
    )
    conn.commit()


def get_mails(owner_id):
    cursor.execute(
        "SELECT id, email FROM mails WHERE owner_id=?",
        (owner_id,)
    )
    return cursor.fetchall()


def get_mail_token(mail_id):
    cursor.execute(
        "SELECT token FROM mails WHERE id=?",
        (mail_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def delete_mail(mail_id):
    cursor.execute("DELETE FROM mails WHERE id=?", (mail_id,))
    conn.commit()


def transfer_owner(new_owner):
    cursor.execute("UPDATE owner SET owner_id=? WHERE id=1", (new_owner,))
    cursor.execute("UPDATE mails SET owner_id=?", (new_owner,))
    conn.commit()


# ================= MAIL API =================
def create_mail(custom_name=None):
    domain_data = requests.get(f"{BASE_URL}/domains").json()
    domain = domain_data["hydra:member"][0]["domain"]

    if custom_name:
        email = f"{custom_name}@{domain}"
    else:
        email = f"user{random.randint(1000,999999)}@{domain}"

    password = "Pass123456"

    acc = requests.post(
        f"{BASE_URL}/accounts",
        json={"address": email, "password": password}
    )

    if acc.status_code != 201:
        return None

    token_data = requests.post(
        f"{BASE_URL}/token",
        json={"address": email, "password": password}
    ).json()

    token = token_data.get("token")

    return email, password, token


# ================= OWNER CHECK =================
def is_owner(user_id):
    owner = get_owner()

    if owner is None:
        set_owner(user_id)
        return True

    return owner == user_id


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📬 Fake Mail Bot\n\n"
        "/generate - create random mail\n"
        "/set <name> - custom mail\n"
        "/id - list mails\n"
        "/transfer <tg_id> - transfer owner"
    )


async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_owner(uid):
        await update.message.reply_text("❌ You are not owner")
        return

    result = create_mail()

    if not result:
        await update.message.reply_text("❌ Failed to create mail")
        return

    email, password, token = result
    add_mail(uid, email, password, token)

    await update.message.reply_text(
        f"✅ New fake mail:\n{email}\n\nUse /id to see list"
    )


async def set_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_owner(uid):
        await update.message.reply_text("❌ You are not owner")
        return

    if not context.args:
        await update.message.reply_text("Usage: /set name")
        return

    custom_name = context.args[0]

    result = create_mail(custom_name)

    if not result:
        await update.message.reply_text("❌ Email already taken")
        return

    email, password, token = result
    add_mail(uid, email, password, token)

    await update.message.reply_text(
        f"✅ Custom mail created:\n{email}"
    )


async def show_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_owner(uid):
        await update.message.reply_text("❌ You are not owner")
        return

    mails = get_mails(uid)

    if not mails:
        await update.message.reply_text("No mails")
        return

    text = "Here are your fake mail ids:\n\n"

    for mail_id, email in mails:
        text += f"{mail_id}. {email} | /delete_{mail_id}\n"

    await update.message.reply_text(text)


async def delete_dynamic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if not is_owner(uid):
        await update.message.reply_text("❌ You are not owner")
        return

    if text.startswith("/delete_"):
        try:
            mail_id = int(text.split("_")[1])
            delete_mail(mail_id)
            await update.message.reply_text(f"✅ Mail {mail_id} deleted")
        except:
            await update.message.reply_text("❌ Invalid delete command")


async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_owner(uid):
        await update.message.reply_text("❌ You are not owner")
        return

    if not context.args:
        await update.message.reply_text("Usage: /transfer <telegram_id>")
        return

    new_owner = int(context.args[0])
    transfer_owner(new_owner)

    await update.message.reply_text(
        f"✅ Ownership transferred to {new_owner}"
    )


# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("set", set_custom))
    app.add_handler(CommandHandler("id", show_ids))
    app.add_handler(CommandHandler("transfer", transfer))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/delete_\d+$"), delete_dynamic))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
