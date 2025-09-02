import json
import random
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# -------------------
# CONFIG
# -------------------
API_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# -------------------
# STORAGE (memory only, production এ database ব্যবহার করো)
# -------------------
user_sessions = {}

# Load area codes
with open("us_ca_areacodes.json", "r") as f:
    AREA_CODES = json.load(f)


# -------------------
# HELPER FUNCTIONS
# -------------------
def get_main_menu(logged_in=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📞 Buy Number"))
    kb.add(KeyboardButton("🎲 Random Area Code"))
    if logged_in:
        kb.add(KeyboardButton("🚪 Logout"))
    else:
        kb.add(KeyboardButton("🔑 Login"))
    return kb


def get_random_area_code():
    return random.choice(list(AREA_CODES.keys()))


def get_numbers_for_area(area_code: str):
    # Demo numbers, বাস্তবে এখানে Twilio API call হবে
    return [f"+1{area_code}{random.randint(2000000, 9999999)}" for _ in range(5)]


# -------------------
# HANDLERS
# -------------------
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
    area = get_random_area_code()
    await message.answer(f"🎲 Random Area Code: {area}\n\nএখন নাম্বার খোঁজা হচ্ছে...")
    numbers = get_numbers_for_area(area)
    for num in numbers:
        await message.answer(num)


@dp.message_handler()
async def handle_all(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Check login input
    if text.startswith("AC") and " " in text:
        sid, token = text.split(" ", 1)
        # এখানে Twilio API দিয়ে validate করতে হবে (ডেমোতে skip)
        user_sessions[user_id] = {"logged_in": True, "sid": sid, "token": token}
        await message.answer(f"🎉 Login সফল!\n✅ Account: <b>{sid}</b>", reply_markup=get_main_menu(True))
        return

    # Area code input
    if text.isdigit() and len(text) in [3]:
        area = text
        if area not in AREA_CODES:
            await message.answer("❌ অবৈধ এরিয়া কোড!")
            return
        await message.answer(f"📍 {AREA_CODES[area]} ({area}) এর জন্য পাওয়া নাম্বার সমূহঃ")
        numbers = get_numbers_for_area(area)
        for num in numbers:
            await message.answer(num)
        return

    # Buy number (user just sends number)
    if text.startswith("+1") and text[2:].isdigit():
        await message.answer(f"✅ নাম্বার সফলভাবে কেনা হয়েছে!\n📞 {text}\n\n👁️ View SMS\n🔄 আবার চেষ্টা করুন")
        return


# -------------------
# RUN
# -------------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
