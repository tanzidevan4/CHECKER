import os
import re
import asyncio
import secrets
from datetime import datetime
from typing import Dict, Any, List, Optional

import aiohttp
from aiohttp import ClientSession

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

API_BASE = "https://api.mail.tm"

BOT_TOKEN = os.environ.get("BOT_TOKEN")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))

if not BOT_TOKEN:
    raise RuntimeError("Environment variable BOT_TOKEN is required. Set it in Railway environment variables.")

# --- MailTM client (minimal) ---
class MailTMClient:
    def __init__(self, session: ClientSession):
        self.session = session

    async def get_domains(self) -> List[Dict[str, Any]]:
        url = f"{API_BASE}/api/v1/domains"
        async with self.session.get(url) as r:
            r.raise_for_status()
            data = await r.json()
            return data.get("hydra:member", [])

    async def create_account(self, address: Optional[str] = None, password: Optional[str] = None) -> Dict[str, str]:
        if not password:
            password = secrets.token_urlsafe(12)
        if not address:
            domains = await self.get_domains()
            if not domains:
                raise RuntimeError("No mail.tm domains available")
            domain = secrets.choice(domains)["domain"]
            username = secrets.token_hex(6)
            address = f"{username}@{domain}"

        payload = {"address": address, "password": password}
        url = f"{API_BASE}/api/v1/accounts"
        async with self.session.post(url, json=payload) as r:
            # mail.tm returns 201 on create, or 400/409 if exists; we'll accept 200/201
            text = await r.text()
            if r.status not in (200, 201):
                # If account exists, still return the chosen address/password (some domains allow create even if exists)
                raise RuntimeError(f"Create account failed: {r.status} {text}")
        return {"address": address, "password": password}

    async def create_token(self, address: str, password: str) -> str:
        url = f"{API_BASE}/api/v1/token"
        payload = {"address": address, "password": password}
        async with self.session.post(url, json=payload) as r:
            r.raise_for_status()
            data = await r.json()
            return data.get("token")

    async def get_messages(self, token: str, page: int = 1) -> Dict[str, Any]:
        url = f"{API_BASE}/api/v1/messages?page={page}"
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.get(url, headers=headers) as r:
            r.raise_for_status()
            return await r.json()

    async def get_message(self, token: str, message_id: str) -> Dict[str, Any]:
        url = f"{API_BASE}/api/v1/messages/{message_id}"
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.get(url, headers=headers) as r:
            r.raise_for_status()
            return await r.json()

# --- In-memory per-user store ---
# Structure:
# user_data = {
#   chat_id: {
#       "address": str,
#       "password": str,
#       "token": str,
#       "seen": set(message_id, ...),
#       "last_getnew": datetime
#   }
# }
user_data: Dict[int, Dict[str, Any]] = {}

# --- OTP extraction regexes (tweakable) ---
OTP_REGEXPS = [
    re.compile(r"\b(\d{4,8})\b"),  # 4-8 digit standalone numbers
    re.compile(r"code[:\s]*([0-9]{4,8})", re.I),
    re.compile(r"verification code[:\s]*([0-9]{4,8})", re.I),
]

def extract_otp(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for rx in OTP_REGEXPS:
        m = rx.search(text)
        if m:
            return m.group(1)
    return None

def format_email_message(message: Dict[str, Any], mail_address: str) -> (str, Optional[str]):
    # message fields commonly: id, from, subject, intro, text, html, createdAt
    msg_id = message.get("id")
    time_str = message.get("createdAt") or message.get("created_at") or datetime.utcnow().isoformat()
    try:
        # normalize iso +Z
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        time_fmt = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        time_fmt = time_str

    from_field = message.get("from") or {}
    sender = from_field.get("address") or from_field.get("name") or "Unknown"

    subject = message.get("subject", "")
    # prioritize text, fallback to intro/html
    body = message.get("text") or message.get("intro") or message.get("html") or ""
    # limit body size to avoid sending giant messages
    body_preview = body if len(body) <= 1500 else body[:1500] + "\n\n[...truncated]"

    otp = extract_otp(body) or extract_otp(subject) or extract_otp(message.get("intro", ""))

    formatted = (
        f"📬 *New Email Received*\n"
        f"🕰 Time: `{time_fmt}`\n"
        f"✉️ Email: `{mail_address}`\n"
        f"📤 From: `{sender}`\n"
        f"📝 Subject: {subject or '_(no subject)_'}\n"
    )
    if otp:
        formatted += f"🔑 OTP: `{otp}`\n"
    formatted += f"---\n✉️ *Full Message:*\n```\n{body_preview}\n```"
    return formatted, otp

# --- Telegram handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Nightmare Worker*\n\n"
        "আমি তোমার temporary-email সহকারী। /getnew কমান্ড দিয়ে নতুন অস্থায়ী ইমেইল তৈরি করো।\n"
        "নতুন মেইল এলে আমি স্বয়ংক্রিয়ভাবে এখানে পাঠিয়ে দেব।\n\n"
        "🔒 টোকেন নিরাপদ রাখো—কখনো শেয়ার করো না।"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def getnew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    app = context.application
    session: ClientSession = app.bot_data.get("http_session")
    mail_client = MailTMClient(session)

    # simple cooldown to prevent abuse (1 minute)
    last = user_data.get(chat_id, {}).get("last_getnew")
    if last:
        delta = (datetime.utcnow() - last).total_seconds()
        if delta < 30:
            await update.message.reply_text("অনুগ্রহ করে একটু অপেক্ষা করুন এবং আবার চেষ্টা করুন (cooldown).")
            return

    try:
        acc = await mail_client.create_account()
        token = await mail_client.create_token(acc["address"], acc["password"])
    except Exception as e:
        await update.message.reply_text(f"অ্যাকাউন্ট তৈরি ব্যর্থ: {e}")
        return

    user_data[chat_id] = {
        "address": acc["address"],
        "password": acc["password"],
        "token": token,
        "seen": set(),
        "last_getnew": datetime.utcnow(),
    }

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔄 Change Email", callback_data="change_email")]]
    )
    await update.message.reply_text(
        f"✅ নতুন ইমেইল তৈরি হলো:\n`{acc['address']}`\n\nChange করলে নতুন ইমেইল পাবে।",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

async def change_email_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    app = context.application
    session: ClientSession = app.bot_data.get("http_session")
    mail_client = MailTMClient(session)
    try:
        acc = await mail_client.create_account()
        token = await mail_client.create_token(acc["address"], acc["password"])
    except Exception as e:
        await query.message.reply_text(f"Email পরিবর্তন ব্যর্থ: {e}")
        return

    user_data[chat_id] = {
        "address": acc["address"],
        "password": acc["password"],
        "token": token,
        "seen": set(),
        "last_getnew": datetime.utcnow(),
    }
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔄 Change Email", callback_data="change_email")]]
    )
    await query.message.reply_text(
        f"🔁 Email পরিবর্তিত হলো: `{acc['address']}`",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

# --- Polling task ---
async def poll_inboxes(app):
    session: ClientSession = app.bot_data.get("http_session")
    mail_client = MailTMClient(session)
    while True:
        try:
            # iterate over copy of items to avoid mutation issues
            for chat_id, data in list(user_data.items()):
                token = data.get("token")
                address = data.get("address")
                if not token or not address:
                    continue
                try:
                    msgs_json = await mail_client.get_messages(token)
                except Exception as e:
                    # token may expire or fail; skip for now
                    # optionally, you could try to re-create token using saved pwd
                    # print(f"get_messages error for {address}: {e}")
                    continue

                members = msgs_json.get("hydra:member", [])
                for msg in members:
                    msg_id = msg.get("id")
                    if not msg_id:
                        continue
                    if msg_id in data.get("seen", set()):
                        continue
                    # fetch full message
                    try:
                        full = await mail_client.get_message(token, msg_id)
                    except Exception:
                        continue
                    formatted, otp = format_email_message(full, address)
                    keyboard = InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔄 Change Email", callback_data="change_email")]]
                    )
                    # send message (use Markdown and code blocks)
                    try:
                        await app.bot.send_message(
                            chat_id=chat_id,
                            text=formatted,
                            parse_mode="Markdown",
                            reply_markup=keyboard,
                        )
                    except Exception:
                        # failed to send (user blocked bot or other); skip
                        pass
                    # mark seen
                    data.setdefault("seen", set()).add(msg_id)
        except Exception as e:
            # top-level poll exception - keep running
            print("Poll loop error:", e)
        await asyncio.sleep(POLL_INTERVAL)

# --- startup/shutdown lifecycle ---
async def on_startup(app):
    # create shared aiohttp session and start poller
    app.bot_data["http_session"] = aiohttp.ClientSession()
    # schedule poll task
    app.create_task(poll_inboxes(app))

async def on_shutdown(app):
    sess: ClientSession = app.bot_data.get("http_session")
    if sess:
        await sess.close()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getnew", getnew))
    app.add_handler(CallbackQueryHandler(change_email_callback, pattern="^change_email$"))

    app.post_init(on_startup)
    app.post_shutdown(on_shutdown)

    # start long-running polling (will block)
    app.run_polling()

if __name__ == "__main__":
    main()
