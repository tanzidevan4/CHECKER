import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from twilio.rest import Client

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # Railway env variable
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_sessions = {}

@dp.message(F.text.startswith("/start") | F.text.startswith("/login"))
async def start(message: Message):
    await message.answer("Send your Twilio SID and Auth Token separated by space:\nSID AUTH_TOKEN")

@dp.message(lambda m: len(m.text.split()) == 2)
async def save_twilio_credentials(message: Message):
    sid, token = message.text.split()
    try:
        client = Client(sid, token)
        account = client.api.accounts(sid).fetch()
        user_sessions[message.from_user.id] = client
        await message.answer(f"Login successful! Account Name: {account.friendly_name}")
        await message.answer("Use /numbers to see your Twilio numbers.")
    except Exception as e:
        await message.answer(f"Failed to login: {e}")

@dp.message(F.text == "/numbers")
async def list_numbers(message: Message):
    client = user_sessions.get(message.from_user.id)
    if not client:
        await message.answer("Login first using /login")
        return
    numbers = client.incoming_phone_numbers.list()
    if not numbers:
        await message.answer("No numbers found.")
    else:
        msg = "Your Twilio Numbers:\n"
        for n in numbers:
            msg += f"- {n.phone_number}\n"
        await message.answer(msg)
        await message.answer("View messages: /messages <number>")

@dp.message(F.text.startswith("/messages"))
async def view_messages(message: Message):
    client = user_sessions.get(message.from_user.id)
    if not client:
        await message.answer("Login first using /login")
        return
    try:
        _, number = message.text.split()
        messages = client.messages.list(to=number, limit=10)
        if not messages:
            await message.answer("No messages on this number.")
        else:
            msg_text = f"Last {len(messages)} messages for {number}:\n"
            for m in messages:
                msg_text += f"From: {m.from_}\nBody: {m.body}\n---\n"
            await message.answer(msg_text)
    except Exception as e:
        await message.answer(f"Error: {e}")

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
