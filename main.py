import asyncio
import logging
import os
import aiohttp
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, শুরুতেই একটি unhandled exception-এর সম্মুখীন হচ্ছিল, যা মূল অ্যাপ্লিকেশনের shutdown প্রক্রিয়াকে বাধাগ্রস্ত করছিল এবং event loop-কে একটি অস্থিতিশীল অবস্থায় রেখে দিচ্ছিল।

**চূড়ান্ত সমাধান (Final Fix):**

এই সমস্যার সমাধান করার জন্য, `poll_sms` ফাংশনটিকে `application` অবজেক্ট গ্রহণ করার জন্য পরিবর্তন করতে CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SMS_API_URL = " হবে এবং সেই অনুযায়ী ফাংশনের ভিতরের কোডও পরিবর্তন করতে হবে।

**পরিবর্তনসমূহ:**
http://174.138.2.82/crapi/had/viewstats"
SMS_1.  `poll_sms` ফাংশনের সিগনেচার পরিবর্তন করে `async def poll_sms(application: Application):` করা হয়েছে।
2.  `poll_sms` ফাংশনের ভিতরে `context.bot`-এর পরিবর্তেAPI_TOKEN = os.environ.get("SMS_API_TOKEN")
POLL_INTERVAL = 8
RECORDS = 50
OTP_MESSAGE_DELETE_DELAY = 180

# --- ADMIN CONFIGURATION ---
 `application.bot` ব্যবহার করা হয়েছে।
3.  `post_init` হুকটি অপরিবর্তিত রাখা হয়েছে, কারণ এটি এখন সঠিকভাবে `application` অবজেক্টটি `poll_sms`-কে পাস করবে।

এইADMIN_IDS = [int(admin_id) for admin_id in os.environ.get("ADMIN_IDS", "").split(',') if admin_id]

# --- USER VERIFICATION CONFIGURATION ---
VERIFY_USER পরিবর্তনটি background task এবং মূল অ্যাপ্লিকেশনের মধ্যে একটি নিখুঁত সামঞ্জস্য তৈরি করবে এবং আপনার পরিবেশের event loop সমস্যাটির স্থায়ী সমাধান করবে।

---

### **সম্পূর্ণ সংশোধিত এবং চূড়ান্ত স্ক্রিপ্ট (Final Fixed Script)**

অনুগ্রহ করে এই সম্পূর্ণ কোডটি ব্যবহার করুন। এটি আপনার সমস্যার সমাধান করবে বলে আমি দৃঢ়ভাবে বিশ্বাস করি।

```python
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

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SMS_API_URL = "http://174.138.2 = True
JOIN_LINKS = [
    {'name': '📢 Our Channel', 'url': 'https://t.me/+bey252hj-qU5ZGNl', 'id': '-1002408654815'},
    {'name': '💬 Discussion Group', 'url': 'https://t.me/+1mrti6CrDyQ5MDY1', 'id': '-1002733230903'}
]

# --- LOGGING SETUP ---
logging.basicConfig(.82/crapi/had/viewstats"
SMS_API_TOKEN = os.environ.get("SMS_API_TOKEN")
POLL_INTERVAL = 8
RECORDS = 50
OTPformat="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- GLOBAL DATA STORE & STATE ---
NUMBER_MESSAGE_DELETE_DELAY = 180

# --- ADMIN CONFIGURATION ---
ADMIN_IDS = [int(admin_id) for admin_id in os.environ.get("ADMIN_IDS", "").split(',') if admin_id]

# --- USER VERIFICATION CONFIGURATION ---
VERIFY_USER = True
JOIN_LIN_DATA = {}
seen_sms = set()
user_chat_ids = set()
assigned_numbers = {}
number_to_user_map = {}
IS_MAINTENANCE_MODE = False
WAITING_FOR_FILE, WAITING_FOR_NAME = range(2)

# --- ALL HELPER,KS = [
    {'name': '📢 Our Channel', 'url': 'https://t.me/+bey252hj-qU5ZGNl', 'id': '-1002408654815'},
    {'name': '💬 Discussion Group', 'url': 'https://t.me/+1mrti6CrDyQ5MDY1', 'id': '-1002733230903'}
]

# --- LOGGING SETUP ---
logging.basicConfig(format="%(asctime)s - %( UI, AND COMMAND HANDLERS ---
def extract_otp(message: str) -> str:
    matches = re.name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__findall(r"\b\d{4,8}\b", message)
    return matches[0] if matchesname__)

# --- GLOBAL DATA STORE & STATE ---
NUMBER_DATA = {}
seen_sms = set()
user_chat_ids = set()
assigned_numbers = {}
number_to_user_map = {}
IS_MAINTENANCE_MODE = False
WAITING_FOR_FILE, WAITING_FOR_NAME = range else "N/A"

async def send_and_schedule_deletion(bot, chat_id, text, delay_seconds):
    try:
        message = await bot.send_message(chat_id=chat_(2)

# --- ALL HELPER, UI, AND COMMAND HANDLERS ---
def extract_otp(message: str) -> str:
    matches = re.findall(r"\b\d{4,8}\id, text=text, parse_mode="HTML")
        await asyncio.sleep(delay_seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    b", message)
    return matches[0] if matches else "N/A"

async def send_andexcept Exception:
        pass

def create_country_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = []_schedule_deletion(bot, chat_id, text, delay_seconds):
    try:
        message = await
    if not NUMBER_DATA:
        buttons.append([InlineKeyboardButton("No numbers available 😔", callback_data="no_op")])
    else:
        for key, data in NUMBER_DATA.items(): bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        await asyncio.sleep(delay_seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    except Exception:
        pass

def create_country_selection_
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
    asynckeyboard() -> InlineKeyboardMarkup:
    buttons = []
    if not NUMBER_DATA:
        buttons.append([InlineKeyboardButton("No numbers available 😔", callback_data="no_op")])
    else:
        for with aiohttp.ClientSession() as session:
        try:
            async with session.get(SMS_API_URL, params=params, timeout=15) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("data", []) if data.get("status") == "success" else []
        except Exception as e:
            logger.error(f"SMS fetch error: {e}")
            return []

async def start_command(update: Update, context: ContextTypes. key, data in NUMBER_DATA.items():
            buttons.append([InlineKeyboardButton(f"{data['button_text']} (Stock: {data.get('stock', 0)})", callback_data=f"country_{key}")])
    buttons.append([InlineKeyboardButton("Refresh List 🔄", callback_data="refresh_list")])DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    if user.id in ADMIN_IDS:
        if chat_id not in user_chat_ids: user_chat_ids.add(chat_id)
        await update.message.reply_text(f"Welcome Admin, {user.first_name}! 👑 Verification bypassed.")
        await update.message.
    return InlineKeyboardMarkup(buttons)

def create_number_options_keyboard(country_key: str) -> Inlinereply_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())
        return
    if IS_MAINTENANCE_MODE:
        await update.message.reply_text("Bot is Under Maintenance, please Wait For A while 🔧"); return
    if chat_id in user_chat_ids:
        await update.message.reply_text("আপনি ইতিমধ্যেই আমাদের বট ব্যবহার করছেন।")
        await update.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country_KeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Change Number 🔄", callback_data=f"change_num_{country_key}")],
        [InlineKeyboardButton("Change Country 🌍", callback_data="change_country")]
    ])

async def fetch_sms():
    params = {"token": SMS_API_TOKEN, "records": RECORDS}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SMS_API_URL, params=params, timeout=15) as resp:
                respselection_keyboard())
    elif VERIFY_USER:
        buttons = [[InlineKeyboardButton(link['name'], url=link['url'])] for link in JOIN_LINKS]
        buttons.append([InlineKeyboardButton("Verify ✅", callback_data="verify_join")])
        await update.message.reply_text(f"Welcome {.raise_for_status()
                data = await resp.json()
                return data.get("datauser.first_name}! 👋\n\nPlease Join Below to use the bot.", reply_markup=InlineKeyboardMarkup(buttons", []) if data.get("status") == "success" else []
        except Exception as e:
            ))
    else:
        user_chat_ids.add(chat_id)
        await update.logger.error(f"SMS fetch error: {e}")
            return []

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; chat_id =message.reply_text(f"Welcome {user.first_name} to Our Bot! 🎉")
        await update.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country update.effective_chat.id
    if user.id in ADMIN_IDS:
        if chat_id not in_selection_keyboard())

async def verify_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if IS_MAINTENANCE_MODE: await query.answer user_chat_ids: user_chat_ids.add(chat_id)
        await update.message("Bot is Under Maintenance 🔧", show_alert=True); return
    user_id = query.from.reply_text(f"Welcome Admin, {user.first_name}! 👑 Verification bypassed.")
        await_user.id
    chat_id = query.message.chat.id
    try:
        is_member = update.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country_ all([(await context.bot.get_chat_member(link['id'], user_id)).status in ['member', 'administrator', 'creator'] for link in JOIN_LINKS])
        if is_member:
            user_selection_keyboard())
        return
    if IS_MAINTENANCE_MODE:
        await update.message.reply_chat_ids.add(chat_id); await query.answer()
            await query.edit_message_text("Bot is Under Maintenance, please Wait For A while 🔧"); return
    if chat_id in usertext("Thanks for joining! 🎉")
            await query.message.reply_text("Select A Country To Get Number 🌍_chat_ids:
        await update.message.reply_text("আপনি ইতিমধ্যেই আমাদের বট ব্যবহার করছেন।")
        await", reply_markup=create_country_selection_keyboard())
        else: await query.answer("❌ You haven update.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country't joined all channels/groups yet!", show_alert=True)
    except Exception as e:
        logger.error(f"Verification error: {e}")
        await query.answer("An error occurred. Please ensure the bot_selection_keyboard())
    elif VERIFY_USER:
        buttons = [[InlineKeyboardButton(link['name'], url=link['url'])] for link in JOIN_LINKS]
        buttons.append([InlineKeyboardButton("Verify ✅", callback_data="verify_join")])
        await update.message.reply_text(f"Welcome { is an admin in the channels.", show_alert=True)

async def user_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if IS_user.first_name}! 👋\n\nPlease Join Below to use the bot.", reply_markup=InlineKeyboardMarkup(buttonsMAINTENANCE_MODE and query.from_user.id not in ADMIN_IDS:
        await query.))
    else:
        user_chat_ids.add(chat_id)
        await update.answer("Bot is Under Maintenance 🔧", show_alert=True); return
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id
    
    async def assignmessage.reply_text(f"Welcome {user.first_name} to Our Bot! 🎉")
        await_new_number(country_key):
        if chat_id in assigned_numbers:
            old_num = assigned update.message.reply_text("Select A Country To Get Number 🌍", reply_markup=create_country_numbers.pop(chat_id)['number']
            if old_num in number_to_user_map: del number_to_user_map[old_num]
        country_data = NUMBER_DATA.get_selection_keyboard())

async def verify_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if IS_MAINTENANCE_MODE: await query.answer(country_key)
        
        if not country_data or not country_data.get('numbers'):("Bot is Under Maintenance 🔧", show_alert=True); return
    user_id = query.from_user.id; chat_id = query.message.chat.id
    try:
        is_member = all
            refresh_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh List 🔄", callback_data="refresh_list")]])
            await query.edit_message_text("Sorry, no numbers are available for this option. 😔", reply([(await context.bot.get_chat_member(link['id'], user_id)).status in ['member', 'administrator', 'creator'] for link in JOIN_LINKS])
        if is_member:
            user_markup=refresh_keyboard)
            return

        new_number = country_data['numbers'].pop(0); country_data['stock'] -= 1
        assigned_numbers[chat_id] = {'number':_chat_ids.add(chat_id); await query.answer()
            await query.edit_message_text("Thanks for joining! 🎉")
            await query.message.reply_text("Select A Country To Get Number 🌍 new_number, 'country_key': country_key}
        number_to_user_map[new_number] = chat_id
        if not country_data['numbers']:
            button_name = country_data['button_text']; del NUMBER_DATA[country_key]
            notification = f"ℹ️ The", reply_markup=create_country_selection_keyboard())
        else: await query.answer("❌ You haven't joined all channels/groups yet!", show_alert=True)
    except Exception as e:
        logger.error( file `'{country_key}.txt'` (Button: `'{button_name}'`) is out of stock andf"Verification error: {e}")
        await query.answer("An error occurred. Please ensure the bot is an admin in the channels.", show_alert=True)

async def user_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if IS_MAINTENANCE_MODE and query.from_user.id not in ADMIN_IDS:
        await query.answer("Bot is Under Maintenance 🔧", show_alert=True); return
    await query.answer(); data = query.data; chat_id = query has been auto-deleted."
            for admin_id in ADMIN_IDS:
                try: await context.bot.send_message(chat_id=admin_id, text=notification)
                except Exception as e: logger.message.chat.id
    
    async def assign_new_number(country_key):
        if.warning(f"Failed to notify admin {admin_id}: {e}")
        text = f"{country_data['button_text']} Number Assigned\n\nNumber: <code>{new_number}</code>"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=create_number_options_keyboard(country_key))
        
    if data.startswith("country_") or data.startswith("change chat_id in assigned_numbers:
            old_num = assigned_numbers.pop(chat_id)['number']
            if old_num in number_to_user_map: del number_to_user_map_num_"):
        key = data.split("_", 1)[1] if data.startswith("country_[old_num]
        country_data = NUMBER_DATA.get(country_key)
        if") else data.split("_", 2)[2]
        await assign_new_number(key)
    elif data == "change_country":
        await query.edit_message_text("Select A Country To Get Number  not country_data or not country_data.get('numbers'):
            refresh_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh List 🔄", callback_data="refresh_list")]])
            await query.edit_message_text("Sorry, no numbers are available for this option. 😔", reply_markup=refresh_keyboard)
            return
        new_number = country_data['numbers'].pop(0); country_data['stock'] -= 1
        assigned🌍", reply_markup=create_country_selection_keyboard())
    elif data == "refresh_list":
        try_numbers[chat_id] = {'number': new_number, 'country_key': country_key}
        number_to_user_map[new_number] = chat_id
        if not country_data['numbers']:
            button_name = country_data['button_text']; del NUMBER_DATA[country_key]
            notification =:
            await query.edit_message_text("Select A Country To Get Number 🌍", reply_markup=create_country_selection_keyboard())
        except Exception as e:
            logger.info(f"Refresh button error (might be no change): {e}")

# --- ADMIN COMMANDS ---

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in f"ℹ️ The file `'{country_key}.txt'` (Button: `'{button_name}'`) is out of stock and has been auto-deleted."
            for admin_id in ADMIN_IDS:
                try: await context.bot.send_message(chat_id=admin_id, text=notification)
                except Exception as e: logger.warning(f"Failed to notify admin {admin_id}: {e}")
        text ADMIN_ID
