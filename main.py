import json
import random
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from twilio.rest import Client

API_TOKEN = "8335359553:AAELrv53ilDiS6vxU3O4b6hy_6vP8KjiXO0"
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

user_sessions = {}

with open("us_ca_areacodes.json", "r") as f:
    AREA_CODES = json.load(f)


def get_main_menu(logged_in=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📞 Buy Number"))
    kb.add(KeyboardButton("🎲 Random Area Code"))
    kb.add(KeyboardButton("📩 My SMS"))
    if logged_in:
        kb.add(KeyboardButton("🚪 Logout"))
    else:
        kb.add(KeyboardButton("🔑 Login"))
    return kb


def get_random_area_code():
    return random.choice(list(AREA_CODES.keys()))


def get_twilio_client(user_id):
    sid = user_sessions[user_id]["sid"]
    token = user_sessions[user_id]["token"]
    return Client(sid, token)


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    logged_in = user_sessions.get(user_id, {}).get("logged_in", False)
    text = "👋 স্বাগতম Twilio Bot-এ!\nএই বটের মাধ্যমে আপনি সহজেই নম্বর কিনতে পারবেন।"
    await message.answer(text, reply_markup=get_main_menu(logged_in))


@dp.message_handler(lambda m: m.text == "🔑 Login")
async def login_start(message: types.Message):
    await message.answer("🛡️ Twilio অ্যাকাউন্ট লগইন করুন!\n➡️ আপনার Twilio এর SID এবং AUTH TOKEN পাঠান:\n\n📌 উদাহরণ:\n<code>ACxxxxxxxxxxxx 1234567890abcdef</code>")


@dp.message_handler(lambda m: m.text == "🚪 Logout")
async def logout_user(message: types.Message):
    user_sessions[message.from_user.id] = {"logged_in": False}
    await message.answer("🚪 আপনি সফলভাবে লগআউট করেছেন।", reply_markup=get_main_menu(False))


@dp.message_handler(lambda m: m.text == "📞 Buy Number")
async def buy_number(message: types.Message):
    await message.answer("🌐 এরিয়া কোড লিখুন (যেমন: 778, 581, 825):")


@dp.message_handler(lambda m: m.text == "🎲 Random Area Code")
async def random_area(message: types.Message):
    user_id = message.from_user.id
    if not user_sessions.get(user_id, {}).get("logged_in", False):
        await message.answer("❌ প্রথমে লগইন করুন।")
        return

    area = get_random_area_code()
    await message.answer(f"🎲 Random Area Code: {area}\n\nএখন নাম্বার খোঁজা হচ্ছে...")

    client = get_twilio_client(user_id)
    numbers = client.available_phone_numbers("US").local.list(
        area_code=area,
        sms_enabled=True,
        voice_enabled=True,
        limit=30
    )

    if not numbers:
        await message.answer("❌ কোনো নম্বর পাওয়া যায়নি।")
        return

    for num in numbers:
        await message.answer(num.phone_number)


@dp.message_handler(lambda m: m.text == "📩 My SMS")
async def my_sms(message: types.Message):
    user_id = message.from_user.id
    if not user_sessions.get(user_id, {}).get("logged_in", False):
        await message.answer("❌ প্রথমে লগইন করুন।")
        return

    client = get_twilio_client(user_id)
    try:
        sms_list = client.messages.list(limit=5)  # সর্বশেষ ৫টা SMS
        if not sms_list:
            await message.answer("📭 এখনো কোনো SMS আসেনি।")
            return

        for sms in sms_list:
            await message.answer(
                f"📩 <b>From:</b> {sms.from_}\n<b>To:</b> {sms.to}\n📝 {sms.body}"
            )
    except Exception as e:
        await message.answer(f"❌ SMS আনতে সমস্যা: {e}")


@dp.message_handler()
async def handle_all(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text.startswith("AC") and " " in text:
        sid, token = text.split(" ", 1)
        try:
            client = Client(sid, token)
            client.api.accounts(sid).fetch()
        except Exception as e:
            await message.answer(f"❌ Login ব্যর্থ: {e}")
            return

        user_sessions[user_id] = {"logged_in": True, "sid": sid, "token": token}
        await message.answer(f"🎉 Login সফল!\n✅ Account: <b>{sid}</b>", reply_markup=get_main_menu(True))
        return

    if text.isdigit() and len(text) == 3:
        if not user_sessions.get(user_id, {}).get("logged_in", False):
            await message.answer("❌ প্রথমে লগইন করুন।")
            return

        area = text
        if area not in AREA_CODES:
            await message.answer("❌ অবৈধ এরিয়া কোড!")
            return

        await message.answer(f"📍 {AREA_CODES[area]} ({area}) এর জন্য পাওয়া নাম্বার সমূহঃ")

        client = get_twilio_client(user_id)
        numbers = client.available_phone_numbers("US").local.list(
            area_code=area,
            sms_enabled=True,
            voice_enabled=True,
            limit=30
        )

        if not numbers:
            await message.answer("❌ কোনো নম্বর পাওয়া যায়নি।")
            return

        for num in numbers:
            await message.answer(num.phone_number)
        return

    if text.startswith("+1") and text[2:].isdigit():
        if not user_sessions.get(user_id, {}).get("logged_in", False):
            await message.answer("❌ প্রথমে লগইন করুন।")
            return

        client = get_twilio_client(user_id)
        try:
            purchased = client.incoming_phone_numbers.create(phone_number=text)
            await message.answer(f"✅ নাম্বার সফলভাবে কেনা হয়েছে!\n📞 {purchased.phone_number}")
        except Exception as e:
            await message.answer(f"❌ কেনা যায়নি: {e}")
        return


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
