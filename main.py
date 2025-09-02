import os
import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from twilio.rest import Client

# Load US+CA area code map
with open("us_ca_areacodes.json") as f:
    AREA_CODE_MAP = json.load(f)

# User sessions: user_id -> {sid, token, friendly_name}
sessions = {}
buy_pending = {}  # user_id -> phone_number awaiting confirmation

# ===== START / WELCOME =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    buttons = []

    if user_id in sessions:
        buttons.append([InlineKeyboardButton("Logout", callback_data="logout")])
        name = sessions[user_id].get("friendly_name", "")
        welcome_text = f"🎉 Login sofol! Account: {name}"
    else:
        buttons.append([InlineKeyboardButton("Login", callback_data="login")])
        welcome_text = "🎉 Welcome to Twilio Bot!"

    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ===== LOGIN =====
async def login_prompt(update_or_query, context):
    await update_or_query.message.reply_text(
        "🛡️ Twilio অ্যাকাউন্ট লগইন করুন!\n\n"
        "➡️ আপনার Twilio এর SID এবং AUTH TOKEN স্পেস সহ পাঠান:\n"
        "📌 উদাহরণ: ACxxxxxxxxxxxx 1234567890abcdef\n\n"
        "⚠️ সতর্কতা: আপনার SID/Token কাউকে শেয়ার করবেন না!"
    )

# Receive SID + Token after login prompt
async def receive_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    parts = text.split()
    if len(parts) != 2 or not parts[0].startswith("AC"):
        await update.message.reply_text("❌ Format ভুল। উদাহরণ অনুযায়ী SID এবং TOKEN পাঠান।")
        return

    sid, token = parts
    client = Client(sid, token)
    try:
        account = client.api.accounts(sid).fetch()
        sessions[user_id] = {"sid": sid, "token": token, "friendly_name": account.friendly_name}
        await update.message.reply_text(f"🎉 Login sofol! Account: {account.friendly_name}")
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")

# ===== LOGOUT =====
async def logout_user(update_or_query, context):
    user_id = update_or_query.from_user.id if hasattr(update_or_query, "from_user") else update_or_query.effective_user.id
    sessions.pop(user_id, None)
    await update_or_query.edit_message_text("🚪 Logged out")

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

    buy_pending[user_id] = text
    keyboard = [
        [InlineKeyboardButton("✅ Yes", callback_data="buy_yes"),
         InlineKeyboardButton("❌ No", callback_data="buy_no")]
    ]
    await update.message.reply_text(f"✅ Do you want to buy {text}?", reply_markup=InlineKeyboardMarkup(keyboard))

# ===== CALLBACK FOR BUY / VIEW SMS / LOGIN / LOGOUT =====
async def callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "buy_yes":
        if user_id not in buy_pending:
            await query.edit_message_text("❌ No number pending for buy.")
            return
        phone_number = buy_pending.pop(user_id)
        sid = sessions[user_id]["sid"]
        token = sessions[user_id]["token"]
        client = Client(sid, token)
        try:
            purchased = client.incoming_phone_numbers.create(phone_number=phone_number)
            keyboard = [[InlineKeyboardButton("📩 View SMS", callback_data=f"view_sms|{phone_number}")]]
            await query.edit_message_text(
                f"✅ Successfully bought {purchased.phone_number}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Failed to buy: {e}")

    elif query.data == "buy_no":
        buy_pending.pop(user_id, None)
        await query.edit_message_text("❌ Purchase cancelled.")

    elif query.data.startswith("view_sms"):
        _, phone_number = query.data.split("|")
        sid = sessions[user_id]["sid"]
        token = sessions[user_id]["token"]
        client = Client(sid, token)
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

    elif query.data == "login":
        await login_prompt(query, context)
    elif query.data == "logout":
        await logout_user(query, context)

# ===== MAIN =====
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login_prompt))
    app.add_handler(CommandHandler("logout", logout_user))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("random", search_random))

    # Message Handler for login credentials and number buy detection
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_login))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, detect_buy))

    # Callback buttons
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
