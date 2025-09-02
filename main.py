import os
import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from twilio.rest import Client

# Load US+CA area code map
with open("us_ca_areacodes.json") as f:
    AREA_CODE_MAP = json.load(f)

sessions = {}  # user_id -> {"sid":..., "token":...}
buy_pending = {}  # user_id -> phone_number awaiting confirmation

# ===== LOGIN =====
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡️ Twilio অ্যাকাউন্ট লগইন করুন!\n\n"
        "➡️ আপনার Twilio এর SID এবং AUTH TOKEN স্পেস সহ পাঠান:\n"
        "📌 উদাহরণ: ACxxxxxxxxxxxx 1234567890abcdef\n\n"
        "⚠️ সতর্কতা: আপনার SID/Token কাউকে শেয়ার করবেন না!"
    )

# Receive SID + Token after login prompt
async def receive_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    parts = update.message.text.strip().split()
    if len(parts) != 2 or not parts[0].startswith("AC"):
        await update.message.reply_text("❌ Format ভুল। উদাহরণ অনুযায়ী SID এবং TOKEN পাঠান।")
        return

    sid, token = parts
    client = Client(sid, token)
    try:
        account = client.api.accounts(sid).fetch()
        sessions[user_id] = {"sid": sid, "token": token}
        await update.message.reply_text(f"✅ Logged in as: {account.friendly_name}")
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")

# ===== SEARCH / RANDOM =====
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /search <area_code>")
        return
    await perform_search(update, context, context.args[0])

async def search_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    area_code = random.choice(list(AREA_CODE_MAP.keys()))
    await perform_search(update, context, area_code, random_search=True)

async def perform_search(update, context, area_code, random_search=False):
    user_id = update.effective_user.id
    if user_id not in sessions:
        await update.message.reply_text("❌ Please /login first")
        return

    country = AREA_CODE_MAP.get(area_code)
    if not country:
        await update.message.reply_text("⚠️ Area code not in US or Canada.")
        return

    sid = sessions[user_id]["sid"]
    token = sessions[user_id]["token"]
    client = Client(sid, token)

    await update.message.reply_text(f"🔍 {area_code} এরিয়া কোড অনুযায়ী নাম্বার খোঁজা হচ্ছে...")

    try:
        numbers = client.available_phone_numbers(country).local.list(
            area_code=area_code,
            sms_enabled=True,
            limit=30
        )
        if not numbers:
            await update.message.reply_text(f"⚠️ No numbers available for {area_code} ({country})")
            return

        heading = f"📍 {country} ({area_code}) এর জন্য পাওয়া নম্বর সমূহ:" 
        await update.message.reply_text(heading)

        # Send each number as separate message
        for n in numbers:
            await update.message.reply_text(n.phone_number)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ===== BUY DETECTION =====
async def detect_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in sessions:
        return
    text = update.message.text.strip()
    if not text.startswith("+1") or not text[1:].isdigit():
        return

    # Ask for confirmation
    buy_pending[user_id] = text
    keyboard = [
        [InlineKeyboardButton("✅ Yes", callback_data="buy_yes"),
         InlineKeyboardButton("❌ No", callback_data="buy_no")]
    ]
    await update.message.reply_text(f"✅ Do you want to buy {text}?", reply_markup=InlineKeyboardMarkup(keyboard))

# ===== CALLBACK FOR BUY =====
async def confirm_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in buy_pending:
        await query.edit_message_text("❌ No number pending for buy.")
        return

    phone_number = buy_pending.pop(user_id)
    sid = sessions[user_id]["sid"]
    token = sessions[user_id]["token"]
    client = Client(sid, token)

    if query.data == "buy_yes":
        try:
            purchased = client.incoming_phone_numbers.create(phone_number=phone_number)
            # Send confirmation + View SMS button
            keyboard = [[InlineKeyboardButton("📩 View SMS", callback_data=f"view_sms|{phone_number}")]]
            await query.edit_message_text(
                f"✅ Successfully bought {purchased.phone_number}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Failed to buy: {e}")
    else:
        await query.edit_message_text("❌ Purchase cancelled.")

# ===== VIEW SMS =====
async def view_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    sid = sessions[user_id]["sid"]
    token = sessions[user_id]["token"]
    client = Client(sid, token)

    _, phone_number = query.data.split("|")
    try:
        messages = client.messages.list(limit=10, direction="inbound")
    except Exception as e:
        await query.edit_message_text(f"⚠️ Error: {e}")
        return

    if not messages:
        await query.edit_message_text("📭 No SMS received yet.")
        return

    reply = f"📩 Latest SMS for {phone_number}:\n\n"
    for msg in messages:
        if msg.to != phone_number:
            continue
        reply += f"From: {msg.from_}\nBody: {msg.body}\n\n"

    await query.edit_message_text(reply if reply.strip() else "📭 No messages for this number.")

# ===== LOGOUT =====
async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("🚪 Logged out.")

# ===== MAIN =====
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("random", search_random))

    # Message Handler for login credentials and number buy detection
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_login))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, detect_buy))

    # Callback buttons
    app.add_handler(CallbackQueryHandler(confirm_buy, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(view_sms, pattern="^view_sms"))

    app.run_polling()

if __name__ == "__main__":
    main()
