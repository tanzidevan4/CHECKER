import asyncio
import logging
import os
import aiohttp
import re
import warnings
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)
from telegram.error import BadRequest

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SMS_API_URL = "http://174.138.2.82/crapi/had/viewstats"
SMS_API_TOKEN = os.environ.get("SMS_API_TOKEN")
POLL_INTERVAL = 8
RECORDS = 50
OTP_MESSAGE_DELETE_DELAY = 180  # 3 minutes

# --- ADMIN CONFIGURATION ---
ADMIN_IDS = [int(i) for i in os.environ.get("ADMIN_IDS", "").split(",") if i]

# --- USER VERIFICATION ---
VERIFY_USER = True
JOIN_LINKS = [
    {"name": "📢 Our Channel", "url": "https://t.me/+bey252hj-qU5ZGNl", "id": "@your_channel_username"},
    {"name": "💬 Discussion Group", "url": "https://t.me/+1mrti6CrDyQ5MDY1", "id": "@your_group_username"},
]

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- GLOBAL STATE ---
NUMBER_DATA = {}
seen_sms = set()
user_chat_ids = set()
assigned_numbers = {}
number_to_user_map = {}
IS_MAINTENANCE_MODE = False
WAITING_FOR_FILE, WAITING_FOR_NAME = range(2)

# --- HELPERS ---
def extract_otp(msg: str) -> str:
    m = re.findall(r"\b\d{4,8}\b", msg)
    return m[0] if m else "N/A"

async def send_and_schedule_deletion(bot, cid, text, delay):
    try:
        m = await bot.send_message(chat_id=cid, text=text, parse_mode="HTML")
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id=cid, message_id=m.message_id)
    except Exception:
        pass

def create_country_selection_keyboard() -> InlineKeyboardMarkup:
    if not NUMBER_DATA:
        return InlineKeyboardMarkup([[InlineKeyboardButton("No numbers available 😔", callback_data="no_op")]])
    buttons = [
        [InlineKeyboardButton(f"{d['button_text']} (Stock: {d.get('stock',0)})", callback_data=f"country_{k}")]
        for k, d in NUMBER_DATA.items()
    ]
    return InlineKeyboardMarkup(buttons)

def create_number_options_keyboard(k: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Change Number 🔄", callback_data=f"change_num_{k}"),
        InlineKeyboardButton("Change Country 🌍", callback_data="change_country")
    ]])

# --- API ---
async def fetch_sms():
    p = {"token": SMS_API_TOKEN, "records": RECORDS}
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(SMS_API_URL, params=p, timeout=20) as r:
                r.raise_for_status()
                d = await r.json()
                return d.get("data", []) if d.get("status") == "success" else []
        except Exception as e:
            logger.error(f"SMS fetch error: {e}")
            return []

# --- USER COMMANDS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    cid = update.effective_chat.id
    if u.id in ADMIN_IDS:
        user_chat_ids.add(cid)
        await update.message.reply_text(f"Welcome Admin, {u.first_name}! 👑")
        await update.message.reply_text("Select a country 🌍", reply_markup=create_country_selection_keyboard())
        return
    if IS_MAINTENANCE_MODE:
        await update.message.reply_text("Bot under maintenance 🔧")
        return
    if cid in user_chat_ids:
        await update.message.reply_text("You’re already verified.")
        await update.message.reply_text("Select a country 🌍", reply_markup=create_country_selection_keyboard())
    elif VERIFY_USER:
        b = [[InlineKeyboardButton(l["name"], url=l["url"])] for l in JOIN_LINKS]
        b.append([InlineKeyboardButton("Verify ✅", callback_data="verify_join")])
        await update.message.reply_text(
            f"Welcome {u.first_name}! 👋\nJoin below to use the bot.",
            reply_markup=InlineKeyboardMarkup(b)
        )
    else:
        user_chat_ids.add(cid)
        await update.message.reply_text(f"Welcome {u.first_name}! 🎉")
        await update.message.reply_text("Select a country 🌍", reply_markup=create_country_selection_keyboard())

async def verify_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if IS_MAINTENANCE_MODE:
        await q.answer("Bot under maintenance 🔧", show_alert=True)
        return
    uid, cid = q.from_user.id, q.message.chat_id
    try:
        ok = all([(await context.bot.get_chat_member(l["id"], uid)).status in ["member","administrator","creator"] for l in JOIN_LINKS])
        if ok:
            user_chat_ids.add(cid)
            await q.answer()
            await q.edit_message_text("✅ Verified!")
            await q.message.reply_text("Select a country 🌍", reply_markup=create_country_selection_keyboard())
        else:
            await q.answer("❌ You haven't joined all!", show_alert=True)
    except Exception as e:
        logger.error(f"Verification error: {e}")
        await q.answer("Error verifying.", show_alert=True)

async def user_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if IS_MAINTENANCE_MODE and q.from_user.id not in ADMIN_IDS:
        await q.answer("Bot under maintenance 🔧", show_alert=True)
        return
    await q.answer()
    data, cid = q.data, q.message.chat_id

    async def assign_new_number(k):
        if cid in assigned_numbers:
            old = assigned_numbers.pop(cid)["number"]
            number_to_user_map.pop(old, None)
        c = NUMBER_DATA.get(k)
        if not c or not c.get("numbers"):
            await q.edit_message_text("No numbers available 😔")
            return
        num = c["numbers"].pop(0)
        c["stock"] -= 1
        assigned_numbers[cid] = {"number": num, "country_key": k}
        number_to_user_map[num] = cid
        if not c["numbers"]:
            btn = c["button_text"]
            del NUMBER_DATA[k]
            for aid in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=aid, text=f"ℹ️ '{btn}' out of stock.")
                except Exception:
                    pass
        text = f"{c['button_text']} assigned\n\nNumber: <code>{num}</code>"
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=create_number_options_keyboard(k))
        await q.message.reply_text(f"⏳ Waiting for OTP <code>{num}</code>", parse_mode="HTML")

    if data.startswith("country_") or data.startswith("change_num_"):
        key = data.split("_", 1)[1] if data.startswith("country_") else data.split("_", 2)[2]
        await assign_new_number(key)
    elif data == "change_country":
        await q.edit_message_text("Select a country 🌍", reply_markup=create_country_selection_keyboard())

# --- ADMIN COMMANDS ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Admin mode activated." if update.effective_user.id in ADMIN_IDS else "❌ Unauthorized.")

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text("Send a .txt file with numbers.")
    return WAITING_FOR_FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".txt"):
        await update.message.reply_text("Invalid file.")
        return WAITING_FOR_FILE
    key = doc.file_name.lower().replace(".txt", "")
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    nums = [f"+{l.strip()}" for l in content.decode("utf-8").splitlines() if l.strip()]
    if not nums:
        await update.message.reply_text("Empty file.")
        return ConversationHandler.END
    context.user_data.update({"temp_numbers": nums, "temp_file_key": key})
    await update.message.reply_text(f"✅ {len(nums)} numbers found. Send button name.")
    return WAITING_FOR_NAME

async def receive_button_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    nums = context.user_data.get("temp_numbers")
    key = context.user_data.get("temp_file_key")
    NUMBER_DATA[key] = {"button_text": name, "numbers": nums, "stock": len(nums), "initial_stock": len(nums)}
    await update.message.reply_text(f"✅ Button '{name}' added ({len(nums)} numbers).")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args:
        if not NUMBER_DATA:
            await update.message.reply_text("No files loaded.")
            return
        msg = "<b>Loaded files:</b>\n" + "\n".join(
            f"• {k}.txt ({d['button_text']})" for k, d in NUMBER_DATA.items())
        await update.message.reply_text(msg, parse_mode="HTML")
        return
    k = context.args[0].lower().replace(".txt", "")
    if k in NUMBER_DATA:
        name = NUMBER_DATA.pop(k)["button_text"]
        await update.message.reply_text(f"✅ Deleted {k}.txt ({name})")
    else:
        await update.message.reply_text("Not found.")

async def used_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    msg = "<b>📊 Used numbers</b>\n"
    for k, d in NUMBER_DATA.items():
        used = d["initial_stock"] - d["stock"]
        msg += f"{k}.txt ({d['button_text']}) → {used}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

async def unused_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    msg = "<b>📦 Remaining stock</b>\n"
    for k, d in NUMBER_DATA.items():
        msg += f"{k}.txt ({d['button_text']}) → {d['stock']}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_MAINTENANCE_MODE
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    IS_MAINTENANCE_MODE = True
    await update.message.reply_text("✅ Maintenance mode enabled.")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_MAINTENANCE_MODE
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    IS_MAINTENANCE_MODE = False
    await update.message.reply_text("✅ Bot resumed.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized.")
        return
    msg = "<b>📋 Buttons</b>\n" + "\n".join(f"• {d['button_text']}" for d in NUMBER_DATA.values())
    await update.message.reply_text(msg if NUMBER_DATA else "No buttons loaded.", parse_mode="HTML")

# --- BACKGROUND POLLING ---
async def poll_sms(app: Application):
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        if not number_to_user_map:
            continue
        try:
            msgs = await fetch_sms()
            if not msgs:
                continue
            for sms in reversed(msgs):
                num = sms["num"] if sms["num"].startswith("+") else f"+{sms['num']}"
                if num in number_to_user_map:
                    sid = f"{sms.get('dt','')}_{num}_{hash(sms.get('message',''))}"
                    if sid in seen_sms:
                        continue
                    seen_sms.add(sid)
                    cid = number_to_user_map.pop(num)
                    assigned_numbers.pop(cid, None)
                    otp = extract_otp(sms["message"])
                    text = (f"✅ <b>NEW OTP DETECTED</b>\n\n⌚ {sms['dt']}\n⚙️ {sms['cli']}\n📱 <code>{num}</code>\n"
                            f"🔑 <code>{otp}</code>\n\n📥 <pre>{sms['message']}</pre>")
                    asyncio.create_task(send_and_schedule_deletion(app.bot, cid, text, OTP_MESSAGE_DELETE_DELAY))
                    await app.bot.send_message(chat_id=cid, text="Your number was used. Select a new one 🌍")
        except Exception as e:
            logger.error(f"poll_sms error: {e}")

# --- MANUAL STARTUP (RAILWAY SAFE) ---
async def main():
    if not all([BOT_TOKEN, SMS_API_TOKEN, ADMIN_IDS]):
        raise RuntimeError("Missing BOT_TOKEN, SMS_API_TOKEN, or ADMIN_IDS.")

    app = Application.builder().token(BOT_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
            WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_button_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    for h in [
        CommandHandler("start", start_command),
        CommandHandler("admin", admin_command),
        add_conv,
        CommandHandler("del", delete_command),
        CommandHandler("used", used_command),
        CommandHandler("unused", unused_command),
        CommandHandler("pause", pause_command),
        CommandHandler("resume", resume_command),
        CommandHandler("status", status_command),
        CallbackQueryHandler(verify_button_callback, pattern="^verify_join$"),
        CallbackQueryHandler(user_button_handler),
    ]:
        app.add_handler(h)

    asyncio.create_task(poll_sms(app))
    logger.info("🚀 Bot is starting...")

    # Manual (no loop close)
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

# --- ENTRYPOINT ---
if __name__ == "__main__":
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.create_task(main())
        loop.run_forever()
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
