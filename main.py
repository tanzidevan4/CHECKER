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
from telegram.request import HTTPXRequest

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SMS_API_URL = "http://174.138.2.82/crapi/had/viewstats"
SMS_API_TOKEN = os.environ.get("SMS_API_TOKEN")
POLL_INTERVAL = 8
RECORDS = 50
OTP_MESSAGE_DELETE_DELAY = 180

# --- ADMIN CONFIGURATION ---
ADMIN_IDS = [int(admin_id) for admin_id in os.environ.get("ADMIN_IDS", "").split(',') if admin_id]

# --- USER VERIFICATION CONFIGURATION ---
VERIFY_USER = True
JOIN_LINKS = [
    {'name': '📢 Our Channel', 'url': 'https://t.me/+bey252hj-qU5ZGNl', 'id': '-1002408654815'},
    {'name': '💬 Discussion Group', 'url': 'https://t.me/+1mrti6CrDyQ5MDY1', 'id': '-1002733230903'}
]

# --- LOGGING SETUP ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- GLOBAL DATA STORE & STATE ---
NUMBER_DATA = {}
seen_sms = set()
user_chat_ids = set()
assigned_numbers = {}
number_to_user_map = {}
IS_MAINTENANCE_MODE = False
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
    buttons.append([InlineKeyboardButton("Refresh List 🔄", callback_data="refresh_list")])
    return InlineKeyboardMarkup(buttons)

def create_number_options_keyboard(country_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Change Number 🔄", callback_data=f"change_num_{country_key}")],
        [InlineKeyboardButton("Change Country 🌍", callback_data="change_country")]
    ])

async def fetch_sms():
    params = {"token": SMS_API_TOKEN, "records": RECORDS}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SMS_API_URL, params=params, timeout=15) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("data", []) if data.get("status") == "success" else []
        except Exception as e:
            logger.error(f"SMS fetch error: {e}")
            return []

# --- USER-FACING HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    if user.id in ADMIN_IDS:
        if chat_id not in user_chat_ids: user_chat_ids.add(chat_id)
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
    chat_id = query.message.chat.id
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
        await query.answer("An error occurred. Please ensure the bot is an admin in the channels.", show_alert=True)

async def user_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if IS_MAINTENANCE_MODE and query.from_user.id not in ADMIN_IDS:
        await query.answer("Bot is Under Maintenance 🔧", show_alert=True)
        return
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id
    
    async def assign_new_number(country_key):
        if chat_id in assigned_numbers:
            old_num = assigned_numbers.pop(chat_id)['number']
            if old_num in number_to_user_map: del number_to_user_map[old_num]
        
        country_data = NUMBER_DATA.get(country_key)
        
        if not country_data or not country_data.get('numbers'):
            refresh_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh List 🔄", callback_data="refresh_list")]])
            await query.edit_message_text("Sorry, no numbers are available for this option. 😔", reply_markup=refresh_keyboard)
            return

        new_number = country_data['numbers'].pop(0)
        country_data['stock'] -= 1
        assigned_numbers[chat_id] = {'number': new_number, 'country_key': country_key}
        number_to_user_map[new_number] = chat_id
        
        if not country_data['numbers']:
            button_name = country_data['button_text']
            del NUMBER_DATA[country_key]
            notification = f"ℹ️ The file `'{country_key}.txt'` (Button: `'{button_name}'`) is out of stock and has been auto-deleted."
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=notification)
                except Exception as e:
                    logger.warning(f"Failed to notify admin {admin_id}: {e}")

        text = f"{country_data['button_text']} Number Assigned\n\nNumber: <code>{new_number}</code>"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=create_number_options_keyboard(country_key))
        
    if data.startswith("country_") or data.startswith("change_num_"):
        key = data.split("_", 1)[1] if data.startswith("country_") else data.split("_", 2)[2]
        await assign_new_number(key)
    elif data == "change_country":
        await query.edit_message_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())
    elif data == "refresh_list":
        try:
            await query.edit_message_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())
        except Exception as e:
            logger.info(f"Refresh button error (might be no change): {e}")

# --- ADMIN COMMANDS ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text("✅ Admin mode activated.")
    else:
        await update.message.reply_text("❌ Unauthorized.")

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("Send the .txt file with numbers.")
    return WAITING_FOR_FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith('.txt'):
        await update.message.reply_text("Invalid file. Please send a .txt file.")
        return WAITING_FOR_FILE
    file_key = doc.file_name.lower().replace('.txt', '')
    if file_key in NUMBER_DATA:
        await update.message.reply_text("⚠️ A file with this name already exists.")
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    numbers = [f"+{line.strip()}" for line in content.decode('utf-8').splitlines() if line.strip()]
    if not numbers:
        await update.message.reply_text("File is empty.")
        return ConversationHandler.END
    context.user_data.update({'temp_numbers': numbers, 'temp_file_key': file_key})
    await update.message.reply_text(f"✅ Found {len(numbers)} numbers. Now, provide the button name.")
    return WAITING_FOR_NAME

async def receive_button_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    nums = context.user_data.get('temp_numbers')
    key = context.user_data.get('temp_file_key')
    initial_count = len(nums)
    NUMBER_DATA[key] = {'button_text': name, 'numbers': nums, 'stock': initial_count, 'initial_stock': initial_count}
    await update.message.reply_text(f"✅ Button '{name}' created with stock {initial_count}.")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args:
        if not NUMBER_DATA:
            await update.message.reply_text("No files to delete.")
            return
        message = "Use `/del file_key` to delete.\n*File key is the filename without .txt*\n\n<b>Available files:</b>\n"
        for key, data in NUMBER_DATA.items():
            message += f"• File Key: <code>{key}</code> (Button: '{data['button_text']}')\n"
        await update.message.reply_text(message, parse_mode="HTML")
    else:
        key_to_delete = context.args[0].lower().replace('.txt', '')
        if key_to_delete in NUMBER_DATA:
            name = NUMBER_DATA.pop(key_to_delete)['button_text']
            await update.message.reply_text(f"✅ File `'{key_to_delete}.txt'` with button `'{name}'` has been deleted.")
        else:
            await update.message.reply_text("❌ File not found.")

async def used_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not NUMBER_DATA:
        await update.message.reply_text("No number files are loaded.")
        return
    message = "<b>📊 Used Number Report</b>\n\n"
    for key, data in NUMBER_DATA.items():
        used = data.get('initial_stock', 0) - data.get('stock', 0)
        message += f"• In `'{key}.txt'` (Button: '{data['button_text']}') Used = <b>{used}</b>\n"
    await update.message.reply_text(message, parse_mode="HTML")

async def unused_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not NUMBER_DATA:
        await update.message.reply_text("No number files are loaded.")
        return
    message = "<b>📦 Unused Number (Stock) Report</b>\n\n"
    for key, data in NUMBER_DATA.items():
        message += f"• In `'{key}.txt'` (Button: '{data['button_text']}') Unused = <b>{data.get('stock', 0)}</b>\n"
    await update.message.reply_text(message, parse_mode="HTML")

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_MAINTENANCE_MODE
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    IS_MAINTENANCE_MODE = True
    await update.message.reply_text("✅ Bot is now in maintenance mode.")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_MAINTENANCE_MODE
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    IS_MAINTENANCE_MODE = False
    await update.message.reply_text("✅ Bot has been resumed.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not NUMBER_DATA:
        await update.message.reply_text("No number files are currently available.")
        return
    message = "<b>📋 Available List</b>\n\n"
    for data in NUMBER_DATA.values():
        message += f"• {data['button_text']}\n"
    await update.message.reply_text(message, parse_mode="HTML")

# --- BACKGROUND TASK ---
async def poll_sms(application: Application):
    """Polls the SMS API and sends OTPs to users."""
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
                    if target_chat_id in assigned_numbers:
                        del assigned_numbers[target_chat_id]
                    otp = extract_otp(sms["message"])
                    text = (f"✅ <b>NEW OTP DETECTED</b>\n\n<b>⌚ Time:</b> {sms['dt']}\n<b>⚙️ Service:</b> {sms['cli']}\n"
                            f"<b>📱 Number:</b> <code>{incoming_number}</code>\n<b>🔑 OTP:</b> <code>{otp}</code>\n\n"
                            f"<b>📥 Full Message:</b>\n<pre>{sms['message']}</pre>")
                    asyncio.create_task(send_and_schedule_deletion(application.bot, target_chat_id, text, OTP_MESSAGE_DELETE_DELAY))
                    await application.bot.send_message(chat_id=target_chat_id, text="Your number has been used and is now released. Select a new one. 🌍")
        except Exception as e:
            logger.error(f"Error in poll_sms loop: {e}")

# --- APPLICATION SETUP & RUN ---
async def post_init(application: Application):
    """A task to run after the bot is initialized, to start the background job."""
    asyncio.create_task(poll_sms(application))

# --- পরিবর্তন এখানে ---
# একটি নতুন এরর হ্যান্ডলার ফাংশন যোগ করা হয়েছে
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error to help with debugging."""
    logger.error("Exception while handling an update:", exc_info=context.error)


def main() -> None:
    if not all([BOT_TOKEN, SMS_API_TOKEN, ADMIN_IDS]):
        logger.critical("Fatal: BOT_TOKEN, SMS_API_TOKEN, and ADMIN_IDS must be set.")
        return
    
    # --- পরিবর্তন এখানে ---
    # নেটওয়ার্কের ধীরগতির জন্য টাইমআউট বাড়ানো হয়েছে
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).request(request).build()
    
    # Add handlers
    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
            WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_button_name)],
        }, fallbacks=[CommandHandler("cancel", cancel)])
    
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
    
    # --- পরিবর্তন এখানে ---
    # এরর হ্যান্ডলারটি অ্যাপ্লিকেশনে যোগ করা হয়েছে
    app.add_error_handler(error_handler)
    
    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot gracefully stopped.")
    except Exception as e:
        logger.critical(f"❌ Bot failed to start: {e}")
