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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

seen = set()

def mask_number(num: str) -> str:
    """ফোন নাম্বার মাস্ক করবে"""
    if len(num) <= 6:
        return num
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

async def poll_sms(app: Application):
    """Continuously polls for new SMS and sends them to the Telegram group."""
    while True:
        try:
            messages = await fetch_sms()
            for sms in reversed(messages):
                sms_id = f"{sms['dt']}_{sms['num']}_{hash(sms['message'])}"
                if sms_id in seen:
                    continue
                seen.add(sms_id)

                masked_num = mask_number(sms["num"])
                otp = extract_otp(sms["message"])

                text = (
                    "✅ <b>NEW OTP DETECTED</b>\n\n"
                    f"<b>⌚ Time:</b> {sms['dt']}\n"
                    f"<b>⚙️ Service:</b> {sms['cli']}\n"
                    f"<b>📱 Number:</b> {masked_num}\n"
                    f"<b>🔑 OTP:</b> <code>{otp}</code>\n"
                    f"<b>📥 Full message:</b>\n{sms['message']}"
                )

                await app.bot.send_message(
                    chat_id=GROUP_CHAT_ID, text=text, parse_mode="HTML"
                )
                logger.info("Sent SMS to Telegram: %s", sms_id)

        except Exception as e:
            logger.error("An error occurred in poll_sms loop: %s", e)

        await asyncio.sleep(POLL_INTERVAL)

async def main():
    """Starts the bot and the SMS polling task."""
    if not all([BOT_TOKEN, SMS_API_TOKEN, GROUP_CHAT_ID]):
        raise RuntimeError("Please set BOT_TOKEN, SMS_API_TOKEN, and GROUP_CHAT_ID environment variables")

    app = Application.builder().token(BOT_TOKEN).build()

    # Start the SMS polling task in the background
    sms_polling_task = asyncio.create_task(poll_sms(app))

    # Run the bot and gracefully handle shutdown
    try:
        logger.info("Starting bot...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logger.info("Bot started successfully. Polling for SMS...")

        # Keep the script running until interrupted (e.g., with Ctrl+C)
        await asyncio.Event().wait()

    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping bot...")

    finally:
        # Gracefully shut down all tasks
        sms_polling_task.cancel()
        if app.updater and app.updater.running:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Bot stopped gracefully.")


if __name__ == "__main__":
   try:
       asyncio.run(main())
   except RuntimeError as e:
       logger.error(f"Failed to start bot: {e}")
   except KeyboardInterrupt:
       logger.info("Process interrupted by user.")
