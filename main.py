import asyncio
import logging
import os
import aiohttp
import re
from telegram.ext import Application

# --- CONFIG ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SMS_API_URL = "http://147.135.212.197/crapi/had/viewstats"
SMS_API_TOKEN = os.environ.get("SMS_API_TOKEN")
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID"))
POLL_INTERVAL = 10
RECORDS = 50
# --------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

seen = set()

def mask_number(num: str) -> str:
    """ফোন নাম্বার মাস্ক করবে"""
    if len(num) <= 6:
        return num  # ছোট হলে মাস্ক না করাই ভালো
    return num[:3] + "****" + num[-3:]

def extract_otp(message: str) -> str:
    """SMS থেকে OTP নাম্বার বের করবে"""
    matches = re.findall(r"\b\d{4,8}\b", message)
    return matches[0] if matches else "N/A"

async def fetch_sms():
    params = {"token": SMS_API_TOKEN, "records": RECORDS}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SMS_API_URL, params=params, timeout=20) as resp:
                data = await resp.json()
                if data.get("status") != "success":
                    logger.warning("API Error: %s", data)
                    return []
                return data.get("data", [])
        except Exception as e:
            logger.error("Fetch error: %s", e)
            return []

async def poll_sms(app):
    while True:
        messages = await fetch_sms()
        for sms in reversed(messages):
            sms_id = f"{sms['dt']}_{sms['num']}_{hash(sms['message'])}"
            if sms_id in seen:
                continue
            seen.add(sms_id)

            masked_num = mask_number(sms["num"])
            otp = extract_otp(sms["message"])

            text = (
                "✅ NEW OTP DETECTED\n\n"
                f"⌚ Time: {sms['dt']}\n"
                f"⚙️ Service: {sms['cli']}\n"
                f"📱 Number: {masked_num}\n"
                f"🔑 OTP: <code>{otp}</code>\n"  # Telegram code formatting (copyable)
                f"📥 Full message:\n{sms['message']}"
            )

            try:
                await app.bot.send_message(
                    chat_id=GROUP_CHAT_ID, text=text, parse_mode="HTML"
                )
                logger.info("Sent SMS: %s", sms_id)
            except Exception as e:
                logger.error("Send error: %s", e)

        await asyncio.sleep(POLL_INTERVAL)

async def main():
    if not all([BOT_TOKEN, SMS_API_TOKEN, GROUP_CHAT_ID]):
        raise RuntimeError("Please set BOT_TOKEN, SMS_API_TOKEN, and GROUP_CHAT_ID environment variables")

    app = Application.builder().token(BOT_TOKEN).build()

    async def on_startup(app):
        # Using create_task is better for background tasks within the application context
        loop = asyncio.get_running_loop()
        loop.create_task(poll_sms(app))

    app.post_init = on_startup
    await app.run_polling()

if __name__ == "__main__":
   # এই অংশটি ঠিক করা হয়েছে
   asyncio.run(main())
