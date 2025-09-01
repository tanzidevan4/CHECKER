import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from twilio.rest import Client

# Store user sessions (per Telegram user)
sessions = {}

# ✅ /login SID TOKEN
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /login <SID> <TOKEN>")
        return

    sid, token = context.args
    client = Client(sid, token)

    try:
        # Test authentication: fetch account info
        account = client.api.accounts(sid).fetch()
        sessions[update.effective_user.id] = {"sid": sid, "token": token}
        await update.message.reply_text(f"✅ Logged in as: {account.friendly_name}")
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")

# 🚪 /logout
async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("🚪 Logged out.")

# 🔍 /search <area_code|random>
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = sessions.get(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Please /login first.")
        return

    sid, token = user["sid"], user["token"]
    client = Client(sid, token)

    if context.args and context.args[0].lower() == "random":
        area_code = random.randint(200, 999)
    else:
        area_code = context.args[0] if context.args else "415"

    try:
        numbers = client.available_phone_numbers("US").local.list(area_code=area_code, limit=5)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")
        return

    if not numbers:
        await update.message.reply_text(f"❌ No numbers found for area code {area_code}")
        return

    reply = f"📞 Available numbers (Area code {area_code}):\n"
    for n in numbers:
        reply += f"{n.phone_number}\n"

    await update.message.reply_text(reply)

# 🛒 /buy +1xxxxxxxxxx
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = sessions.get(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Please /login first.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /buy <phone_number>")
        return

    phone_number = context.args[0]
    keyboard = [
        [InlineKeyboardButton("✅ Yes", callback_data=f"buy_yes|{phone_number}"),
         InlineKeyboardButton("❌ No", callback_data="buy_no")]
    ]
    await update.message.reply_text(
        f"Do you want to buy {phone_number}?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Confirmation callback
async def confirm_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = sessions.get(update.effective_user.id)
    if not user:
        await query.edit_message_text("❌ Please /login first.")
        return

    sid, token = user["sid"], user["token"]
    client = Client(sid, token)

    action, phone_number = query.data.split("|") if "|" in query.data else (query.data, None)

    if action == "buy_yes" and phone_number:
        try:
            purchased = client.incoming_phone_numbers.create(phone_number=phone_number)
            await query.edit_message_text(f"✅ Successfully bought {purchased.phone_number}")
        except Exception as e:
            await query.edit_message_text(f"❌ Failed to buy: {e}")
    else:
        await query.edit_message_text("❌ Purchase cancelled.")

# 📩 /inbox [optional: +1xxxxxxxxxx]
async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = sessions.get(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Please /login first.")
        return

    sid, token = user["sid"], user["token"]
    client = Client(sid, token)

    filter_number = context.args[0] if context.args else None
    try:
        messages = client.messages.list(limit=10)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")
        return

    if not messages:
        await update.message.reply_text("📭 No SMS received yet.")
        return

    reply = "📩 Latest SMS:\n\n"
    for msg in messages:
        if filter_number and msg.to != filter_number:
            continue
        reply += f"From: {msg.from_}\nTo: {msg.to}\nBody: {msg.body}\n\n"

    await update.message.reply_text(reply if reply.strip() else "📭 No messages for this number.")

# ▶️ Main
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN not set in environment variables")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("inbox", inbox))
    app.add_handler(CallbackQueryHandler(confirm_buy))

    app.run_polling()

if __name__ == "__main__":
    main()
