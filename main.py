import asyncio
import logging
import os
import aiohttp
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)
from telegram.error import BadRequest

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SMS_API_URL = "http://174.138.2.82/crapi/had/viewstats"
SMS_API_TOKEN = os.environ.get("SMS_API_TOKEN")
POLL_INTERVAL = 8  # seconds
RECORDS = 50
OTP_MESSAGE_DELETE_DELAY = 180  # 3 minutes

# --- ADMIN CONFIGURATION ---
# আপনার টেলিগ্রাম ইউজার আইডি এখানে যোগ করুন। @userinfobot থেকে আইডি নিন।
ADMIN_IDS = [int(admin_id) for admin_id in os.environ.get("ADMIN_IDS", "").split(',') if admin_id]

# --- USER VERIFICATION CONFIGURATION ---
VERIFY_USER = True 
JOIN_LINKS = [
    {'name': '📢 Our Channel', 'url': 'https://t.me/your_channel_username', 'id': '@your_channel_username'},
    {'name': '💬 Discussion Group', 'url': 'https://t.me/your_group_username', 'id': '@your_group_username'}
]

# --- LOGGING SETUP ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- GLOBAL DATA STORE & STATE ---
NUMBER_DATA = {}
seen_sms = set()
user_chat_ids = set()
assigned_numbers = {} 
number_to_user_map = {}
IS_MAINTENANCE_MODE = False

# --- CONVERSATION HANDLER STATES ---
WAITING_FOR_FILE, WAITING_FOR_NAME = range(2)

# --- HELPER & UI FUNCTIONS ---
def extract_otp(message: str) -> str:
    matches = re.findall(r"\b\d{4,8}\b", message)
    return matches[0] if matches else "N/A"

async def send_and_schedule_deletion(bot, chat_id, text, delay_seconds):
    try:
        message = await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        await asyncio.sleep(delay_seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    except Exception:
        pass

def create_country_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    if not NUMBER_DATA:
        buttons.append([InlineKeyboardButton("No numbers available 😔", callback_data="no_op")])
    else:
        for key, data in NUMBER_DATA.items():
            buttons.append([InlineKeyboardButton(f"{data['button_text']} (Stock: {data.get('stock', 0)})", callback_data=f"country_{key}")])
    return InlineKeyboardMarkup(buttons)

def create_number_options_keyboard(country_key: str) -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton("Change Number 🔄", callback_data=f"change_num_{country_key}"),
        InlineKeyboardButton("Change Country 🌍", callback_data="change_country")
    ]]
    return InlineKeyboardMarkup(buttons)

# --- CORE API FUNCTION ---
async def fetch_sms():
    params = {"token": SMS_API_TOKEN, "records": RECORDS}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SMS_API_URL, params=params, timeout=20) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("data", []) if data.get("status") == "success" else []
        except Exception as e:
            logger.error(f"SMS fetch error: {e}")
            return []

# --- USER COMMANDS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    if user.id in ADMIN_IDS:
        user_chat_ids.add(chat_id)
        await update.message.reply_text(f"Welcome Admin, {user.first_name}! 👑 Verification bypassed.")
        await update.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())
        return

    if IS_MAINTENANCE_MODE:
        await update.message.reply_text("Bot is Under Maintenance, please Wait For A while 🔧")
        return
        
    if chat_id in user_chat_ids:
        await update.message.reply_text("আপনি ইতিমধ্যেই আমাদের বট ব্যবহার করছেন।")
        await update.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())
    elif VERIFY_USER:
        buttons = [[InlineKeyboardButton(link['name'], url=link['url'])] for link in JOIN_LINKS]
        buttons.append([InlineKeyboardButton("Verify ✅", callback_data="verify_join")])
        await update.message.reply_text(f"Welcome {user.first_name}! 👋\n\nPlease Join Below to use the bot.", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        user_chat_ids.add(chat_id)
        await update.message.reply_text(f"Welcome {user.first_name} to Our Bot! 🎉")
        await update.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())

async def verify_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if IS_MAINTENANCE_MODE:
        await query.answer("Bot is Under Maintenance 🔧", show_alert=True)
        return
        
    user_id = query.from_user.id
    chat_id = query.effective_chat.id
    try:
        is_member = all([(await context.bot.get_chat_member(link['id'], user_id)).status in ['member', 'administrator', 'creator'] for link in JOIN_LINKS])
        if is_member:
            user_chat_ids.add(chat_id)
            await query.answer()
            await query.edit_message_text("Thanks for joining! 🎉")
            await query.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())
        else:
            await query.answer("❌ You haven't joined all channels/groups yet!", show_alert=True)
    except Exception as e:
        logger.error(f"Verification error: {e}")
        await query.answer("An error occurred.", show_alert=True)

async def user_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if IS_MAINTENANCE_MODE and query.from_user.id not in ADMIN_IDS:
        await query.answer("Bot is Under Maintenance 🔧", show_alert=True)
        return
    await query.answer()
    data = query.data
    chat_id = query.effective_chat.id

    async def assign_new_number(country_key):
        if chat_id in assigned_numbers:
            old_num = assigned_numbers.pop(chat_id)['number']
            number_to_user_map.pop(old_num, None)
        
        country_data = NUMBER_DATA.get(country_key)
        if not country_data or not country_data.get('numbers'):
            await query.edit_message_text("Sorry, no numbers are available for this option. 😔")
            return
        
        new_number = country_data['numbers'].pop(0)
        country_data['stock'] -= 1
        assigned_numbers[chat_id] = {'number': new_number, 'country_key': country_key}
        number_to_user_map[new_number] = chat_id
        
        if not country_data['numbers']:
            button_name = country_data['button_text']
            del NUMBER_DATA[country_key]
            notification = f"ℹ️ The file '{country_key}.txt' (Button: '{button_name}') is out of stock and auto-deleted."
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=notification)
                except Exception as e:
                    logger.warning(f"Failed to notify admin {admin_id}: {e}")

        text = f"{country_data['button_text']} Number Assigned\n\nNumber: <code>{new_number}</code>"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=create_number_options_keyboard(country_key))
        await query.message.reply_text(f"⏳ Waiting for an OTP for <code>{new_number}</code>.", parse_mode="HTML")

    if data.startswith("country_") or data.startswith("change_num_"):
        key = data.split("_", 1)[1] if data.startswith("country_") else data.split("_", 2)[2]
        await assign_new_number(key)
    elif data == "change_country":
        await query.edit_message_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())

# --- ADMIN COMMANDS (same as before) ---
# [Omitted here for brevity — your admin commands and polling logic remain unchanged]
# (use the same code you already had for add, del, used, unused, pause, resume, status, etc.)

# --- BACKGROUND POLLING TASK ---
async def poll_sms(app: Application):
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        if not number_to_user_map:
            continue
        try:
            messages = await fetch_sms()
            if not messages:
                continue
            for sms in reversed(messages):
                incoming_number = sms['num'] if sms['num'].startswith('+') else f"+{sms['num']}"
                if incoming_number in number_to_user_map:
                    sms_id = f"{sms.get('dt','')}_{incoming_number}_{hash(sms.get('message',''))}"
                    if sms_id in seen_sms:
                        continue
                    seen_sms.add(sms_id)
                    target_chat_id = number_to_user_map.pop(incoming_number)
                    assigned_numbers.pop(target_chat_id, None)
                    
                    otp = extract_otp(sms["message"])
                    text = (f"✅ <b>NEW OTP DETECTED</b>\n\n<b>⌚ Time:</b> {sms['dt']}\n<b>⚙️ Service:</b> {sms['cli']}\n"
                            f"<b>📱 Number:</b> <code>{incoming_number}</code>\n<b>🔑 OTP:</b> <code>{otp}</code>\n\n"
                            f"<b>📥 Full Message:</b>\n<pre>{sms['message']}</pre>")
                    
                    asyncio.create_task(send_and_schedule_deletion(app.bot, target_chat_id, text, OTP_MESSAGE_DELETE_DELAY))
                    await app.bot.send_message(chat_id=target_chat_id, text="Your number has been used and released. Select a new one 🌍")
        except Exception as e:
            logger.error(f"Error in poll_sms loop: {e}")

# --- MAIN APP ---
async def main():
    if not all([BOT_TOKEN, SMS_API_TOKEN, ADMIN_IDS]):
        raise RuntimeError("Fatal: BOT_TOKEN, SMS_API_TOKEN, and ADMIN_IDS must be set.")
    
    app = Application.builder().token(BOT_TOKEN).build()

    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
            WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_button_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(add_conv_handler)
    app.add_handler(CommandHandler("del", delete_command))
    app.add_handler(CommandHandler("used", used_command))
    app.add_handler(CommandHandler("unused", unused_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(verify_button_callback, pattern="^verify_join$"))
    app.add_handler(CallbackQueryHandler(user_button_handler))

    asyncio.create_task(poll_sms(app))

    logger.info("🚀 Bot is starting...")
    await app.run_polling()

# --- RAILWAY-SAFE ENTRYPOINT ---
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Railway or async container already has a loop
            loop.create_task(main())
            loop.run_forever()
        else:
            loop.run_until_complete(main())
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
