import asyncio
import requests
import os
import re
import html
import sqlite3
import time
import sys
from datetime import datetime
from telegram import Bot

# === CONFIGURATION ===
# আপনার ব্যক্তিগত তথ্যগুলো এখন Environment Variable থেকে লোড করা হচ্ছে
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
API_TOKEN = os.getenv('API_TOKEN') # নতুন: আপনার API টোকেন এখানে লোড হবে

# Check if all required environment variables are set
if not all([BOT_TOKEN, CHAT_ID, API_TOKEN]):
    print("ত্রুটি: প্রয়োজনীয় Environment Variables (BOT_TOKEN, CHAT_ID, API_TOKEN) সেট করা নেই।")
    sys.exit(1) # Exit the script with an error code

# নতুন API URL
API_URL = "http://147.135.212.197/crapi/had/viewstats"

# === COUNTRY CODE MAP ===
COUNTRY_MAP = {
    '1': '🇺🇸 USA / Canada', '7': '🇷🇺 Russia / Kazakhstan', '20': '🇪🇬 Egypt', '27': '🇿🇦 South Africa',
    '30': '🇬🇷 Greece', '31': '🇳🇱 Netherlands', '32': '🇧🇪 Belgium', '33': '🇫🇷 France', '34': '🇪🇸 Spain',
    '36': '🇭🇺 Hungary', '39': '🇮🇹 Italy', '40': '🇷🇴 Romania', '41': '🇨🇭 Switzerland', '43': '🇦🇹 Austria',
    '44': '🇬🇧 United Kingdom', '45': '🇩🇰 Denmark', '46': '🇸🇪 Sweden', '47': '🇳🇴 Norway', '48': '🇵🇱 Poland',
    '49': '🇩🇪 Germany', '51': '🇵🇪 Peru', '52': '🇲🇽 Mexico', '53': '🇨🇺 Cuba', '54': '🇦🇷 Argentina',
    '55': '🇧🇷 Brazil', '56': '🇨🇱 Chile', '57': '🇨🇴 Colombia', '58': '🇻🇪 Venezuela', '60': '🇲🇾 Malaysia',
    '61': '🇦🇺 Australia', '62': '🇮🇩 Indonesia', '63': '🇵🇭 Philippines', '64': '🇳🇿 New Zealand',
    '65': '🇸🇬 Singapore', '66': '🇹🇭 Thailand', '81': '🇯🇵 Japan', '82': '🇰🇷 South Korea', '84': '🇻🇳 Vietnam',
    '86': '🇨🇳 China', '90': '🇹🇷 Turkey', '91': '🇮🇳 India', '92': '🇵🇰 Pakistan', '93': '🇦🇫 Afghanistan',
    '94': '🇱🇰 Sri Lanka', '95': '🇲🇲 Myanmar', '98': '🇮🇷 Iran', '211': '🇸🇸 South Sudan', '212': '🇲🇦 Morocco',
    '213': '🇩🇿 Algeria', '216': '🇹🇳 Tunisia', '218': '🇱🇾 Libya', '220': '🇬🇲 Gambia', '221': '🇸🇳 Senegal',
    '222': '🇲🇷 Mauritania', '223': '🇲🇱 Mali', '224': '🇬🇳 Guinea', '225': '🇨🇮 Côte d\'Ivoire', '226': '🇧🇫 Burkina Faso',
    '227': '🇳🇪 Niger', '228': '🇹🇬 Togo', '229': '🇧🇯 Benin', '230': '🇲🇺 Mauritius', '231': '🇱🇷 Liberia',
    '232': '🇸🇱 Sierra Leone', '233': '🇬🇭 Ghana', '234': '🇳🇬 Nigeria', '235': '🇹🇩 Chad', '236': '🇨🇫 Central African Republic',
    '237': '🇨🇲 Cameroon', '238': '🇨🇻 Cape Verde', '239': '🇸🇹 Sao Tome & Principe', '240': '🇬🇶 Equatorial Guinea',
    '241': '🇬🇦 Gabon', '242': '🇨🇬 Congo', '243': '🇨🇩 DR Congo', '244': '🇦🇴 Angola', '249': '🇸🇩 Sudan',
    '250': '🇷🇼 Rwanda', '251': '🇪🇹 Ethiopia', '252': '🇸🇴 Somalia', '253': '🇩🇯 Djibouti', '254': '🇰🇪 Kenya',
    '255': '🇹🇿 Tanzania', '256': '🇺🇬 Uganda', '257': '🇧🇮 Burundi', '258': '🇲🇿 Mozambique', '260': '🇿🇲 Zambia',
    '261': '🇲🇬 Madagascar', '263': '🇿🇼 Zimbabwe', '264': '🇳🇦 Namibia', '265': '🇲🇼 Malawi', '266': '🇱🇸 Lesotho',
    '267': '🇧🇼 Botswana', '268': '🇸🇿 Eswatini', '269': '🇰🇲 Comoros', '290': '🇸🇭 Saint Helena', '291': '🇪🇷 Eritrea',
    '297': '🇦🇼 Aruba', '298': '🇫🇴 Faroe Islands', '299': '🇬🇱 Greenland', '350': '🇬🇮 Gibraltar', '351': '🇵🇹 Portugal',
    '352': '🇱🇺 Luxembourg', '353': '🇮🇪 Ireland', '354': '🇮🇸 Iceland', '355': '🇦🇱 Albania', '356': '🇲🇹 Malta',
    '357': '🇨🇾 Cyprus', '358': '🇫🇮 Finland', '359': '🇧🇬 Bulgaria', '370': '🇱🇹 Lithuania', '371': '🇱🇻 Latvia',
    '372': '🇪🇪 Estonia', '373': '🇲🇩 Moldova', '374': '🇦🇲 Armenia', '375': '🇧🇾 Belarus', '376': '🇦🇩 Andorra',
    '377': '🇲🇨 Monaco', '378': '🇸🇲 San Marino', '380': '🇺🇦 Ukraine', '381': '🇷🇸 Serbia', '382': '🇲🇪 Montenegro',
    '383': '🇽🇰 Kosovo', '385': '🇭🇷 Croatia', '386': '🇸🇮 Slovenia', '387': '🇧🇦 Bosnia & Herzegovina',
    '389': '🇲🇰 North Macedonia', '420': '🇨🇿 Czech Republic', '421': '🇸🇰 Slovakia', '423': '🇱🇮 Liechtenstein',
    '852': '🇭🇰 Hong Kong', '853': '🇲🇴 Macau', '855': '🇰🇭 Cambodia', '856': '🇱🇦 Laos', '880': '🇧🇩 Bangladesh',
    '886': '🇹🇼 Taiwan', '960': '🇲🇻 Maldives', '961': '🇱🇧 Lebanon', '962': '🇯🇴 Jordan', '963': '🇸🇾 Syria',
    '964': '🇮🇶 Iraq', '965': '🇰🇼 Kuwait', '966': '🇸🇦 Saudi Arabia', '967': '🇾🇪 Yemen', '968': '🇴🇲 Oman',
    '970': '🇵🇸 Palestine', '971': '🇦🇪 UAE', '972': '🇮🇱 Israel', '973': '🇧🇭 Bahrain', '974': '🇶🇦 Qatar',
    '975': '🇧🇹 Bhutan', '976': '🇲🇳 Mongolia', '977': '🇳🇵 Nepal', '992': '🇹🇯 Tajikistan', '993': '🇹🇲 Turkmenistan',
    '994': '🇦🇿 Azerbaijan', '995': '🇬🇪 Georgia', '996': '🇰🇬 Kyrgyzstan', '998': '🇺🇿 Uzbekistan'
}

# Telegram bot
bot = Bot(token=BOT_TOKEN)

# === DATABASE FUNCTIONS ===
DB_NAME = "otp_history.db"
def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS sent_otps (otp_key TEXT PRIMARY KEY, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

def is_otp_already_sent(otp_key):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sent_otps WHERE otp_key = ?", (otp_key,))
    exists = cursor.fetchone()
    conn.close()
    return exists is not None

def add_otp_to_db(otp_key):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sent_otps (otp_key) VALUES (?)", (otp_key,))
    conn.commit()
    conn.close()

# === HELPER FUNCTIONS ===
def get_country_from_number(number: str) -> str:
    for code in sorted(COUNTRY_MAP.keys(), key=len, reverse=True):
        if number.startswith(code):
            return COUNTRY_MAP[code]
    return '🌍 Unknown Country'

def mask_number(number_str: str) -> str:
    if len(number_str) > 9:
        return f"{number_str[:5]}****{number_str[-4:]}"
    return number_str

# === CORE NETWORK FUNCTION (UPDATED) ===
def fetch_data():
    """Fetches the latest records from the new API."""
    params = {
        'token': API_TOKEN,
        'records': 100  # Fetch latest 100 records to avoid missing any
    }
    try:
        # Using simple requests.get as session is no longer needed for login
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        data = resp.json()
        if data.get('status') == 'success':
            return data
        else:
            print(f"API Error: {data.get('msg', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Network error during data fetch: {e}")
        return None
    except ValueError: # Catches JSON decoding errors
        print("Failed to decode JSON from response.")
        return None

# === TELEGRAM SENDER ===
async def send_to_telegram(date, number, service, otp, message):
    country_info = get_country_from_number(number)
    country_parts = country_info.split(' ', 1)
    country_emoji = country_parts[0]
    country_name = country_parts[1].split(' / ')[0]
    masked_number = mask_number(number)
    
    safe_service = html.escape(service)
    safe_otp = html.escape(otp)
    safe_message = html.escape(message)

    title = f"🔔 {country_emoji} <b>{country_name}</b> {safe_service} OТP Received..."

    body_lines = [
        f"<blockquote>🕰 Time: {date}</blockquote>",
        f"<blockquote>🌍 Country: {country_info}</blockquote>",
        f"<blockquote>📱 Service: {safe_service}</blockquote>",
        f"<blockquote>📞 Number: {masked_number}</blockquote>",
        f"<blockquote>🔑 OTP: {safe_otp}</blockquote>",
        f"<blockquote>✉️ Full Message:</blockquote>",
        f"<blockquote># {safe_message}</blockquote>"
    ]
    
    body = "\n".join(body_lines)
    full_message = f"{title}\n\n{body}"

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=full_message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        print("Message Sent")
    except Exception as e:
        print(f"Telegram send error: {e}")

# === MAIN LOOP (UPDATED) ===
async def main_loop():
    setup_database()
    print("Bot started with API integration.")
    
    while True:
        data = fetch_data()
        # Process data if fetch was successful and status is 'success'
        if data and data.get('status') == 'success':
            # Reverse the list to process oldest OTPs first
            for item in reversed(data.get('data', [])):
                # Extract data based on new JSON structure
                date = item.get('dt')
                number = item.get('num')
                service = item.get('cli')
                message = html.unescape(item.get('message', ''))

                if not all([date, number, service, message]):
                    continue # Skip if essential data is missing

                # OTP finding logic remains the same
                match = re.search(r"\b\d{3}-\d{3}\b|\b\d{4,8}\b", message) # Regex slightly improved
                otp = match.group() if match else None
                
                if otp:
                    # Database check remains the same
                    key = f"{number}|{otp}|{date}" # Adding date to key for better uniqueness
                    if not is_otp_already_sent(key):
                        add_otp_to_db(key)
                        await send_to_telegram(date, number, service, otp, message)
        
        await asyncio.sleep(5) # Wait for 5 seconds before next API call

# === START BOT ===
if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nBot stopped.")
