import os
import re
import secrets
import asyncio
from datetime import datetime
from typing import Dict, Any

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
POLL_INTERVAL = 15  # seconds

if not BOT_TOKEN:
    raise RuntimeError("⚠️ BOT_TOKEN environment variable is required.")

# --- in-memory user data store ---
user_data: Dict[int, Dict[str, Any]] = {}

# --- OTP regex ---
OTP_REGEX = re.compile(r"\b(\d{4,8})\b")

def extract_otp(text: str):
    match = OTP_REGEX.search(text)
    return match.group(1) if match else None

# --- MailTM minimal client ---
class MailTMClient:
    BASE = "https://api.mail.tm"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def get_domains(self):
        async with self.session.get(f"{self.BASE}/api/v1/domains") as r:
            r.raise_for_status()
            data = await r.json()
            return data.get("hydra:member", [])

    async def create_account(self):
        domains = await self.get_domains()
        domain = secrets.choice(domains)["domain"]
        username = secrets.token_hex(6)
        address = f"{username}@{domain}"
        password = secrets.token_urlsafe(12)
        payload = {"address": address, "password": password}
        async with self.session.post(f"{self.BASE}/api/v1/accounts", json=payload) as r:
            if r.status not in (200, 201):
                text = await r.text()
                raise RuntimeError(f"Create account failed: {r.status} {text}")
        async with self.session.post(f"{self.BASE}/api/v1/token", json={"address": address, "password": password}) as r:
            r.raise_for_status()
            token = (await r.json())["token"]
        return address, password, token

    async def get_messages(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.get(f"{self.BASE}/api/v1/messages", headers=headers) as r:
            r.raise_for_status()
            return (await r.json()).get("hydra:member", [])

    async def get_message(self, token, msg_id):
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.get(f"{self.BASE}/api/v1/messages/{msg_id}", headers=headers) as r:
            r.raise_for_status()
            return await r.json()

# --- Telegram handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Nightmare Worker*\n\n"
        "আমি তোমার temporary-email সহকারী। /getnew কমান্ড দিয়ে নতুন ইমেইল তৈরি করো।\n"
        "নতুন মেইল এলে আমি স্বয়ংক্রিয়ভাবে এখানে পাঠিয়ে দেব।",
        parse_mode="Markdown"
    )

async def getnew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session: aiohttp.ClientSession = context.application.bot_data["http_session"]
    client = MailTMClient(session)
    try:
        address, password, token = await client.create_account()
    except Exception as e:
        await update.message.reply_text(f"অ্যাকাউন্ট তৈরি ব্যর্থ: {e}")
        return
    user_data[chat_id] = {"address": address, "password": password, "token": token, "seen": set()}
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Change Email", callback_data="change_email")]])
    await update.message.reply_text(f"✅ নতুন ইমেইল:\n`{address}`", parse_mode="Markdown", reply_markup=keyboard)

async def change_email_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    session: aiohttp.ClientSession = context.application.bot_data["http_session"]
    client = MailTMClient(session)
    try:
        address, password, token = await client.create_account()
    except Exception as e:
        await query.message.reply_text(f"Email পরিবর্তন ব্যর্থ: {e}")
        return
    user_data[chat_id] = {"address": address, "password": password, "token": token, "seen": set()}
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Change Email", callback_data="change_email")]])
    await query.message.reply_text(f"🔁 Email পরিবর্তিত হলো: `{address}`", parse_mode="Markdown", reply_markup=keyboard)

# --- Inbox polling ---
async def poll_inboxes(app):
    session: aiohttp.ClientSession = app.bot_data["http_session"]
    client = MailTMClient(session)
    while True:
        for chat_id, data in list(user_data.items()):
            token = data["token"]
            address = data["address"]
            try:
                messages = await client.get_messages(token)
            except:
                continue
            for msg in messages:
                msg_id = msg["id"]
                if msg_id in data["seen"]:
                    continue
                full = await client.get_message(token, msg_id)
                otp = extract_otp(full.get("text") or full.get("intro") or "")
                time_fmt = full.get("createdAt", "")
                from_addr = full.get("from", {}).get("address", "Unknown")
                subject = full.get("subject", "")
                body = full.get("text") or full.get("intro") or ""
                body_preview = body if len(body) < 1000 else body[:1000]+"..."
                text = f"📬 *New Email*\n🕰 `{time_fmt}`\n✉️ `{address}`\n📤 `{from_addr}`\n📝 {subject}\n"
                if otp: text += f"🔑 OTP: `{otp}`\n"
                text += f"---\n```\n{body_preview}\n```"
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Change Email", callback_data="change_email")]])
                try:
                    await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=keyboard)
                except:
                    continue
                data["seen"].add(msg_id)
        await asyncio.sleep(POLL_INTERVAL)

# --- Start bot ---
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getnew", getnew))
    app.add_handler(CallbackQueryHandler(change_email_callback, pattern="^change_email$"))
    app.bot_data["http_session"] = aiohttp.ClientSession()
    asyncio.create_task(poll_inboxes(app))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
