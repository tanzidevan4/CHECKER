import logging
import re
from datetime import datetime
from tempmail import TempMail

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler

# লগিং চালু করা হচ্ছে
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# স্টার্ট কমান্ড হ্যান্ডলার
def start(update: Update, context: CallbackContext) -> None:
    """/start কমান্ড দিলে এই ফাংশনটি কাজ করবে।"""
    welcome_message = """
👋 *স্বাগতম!*

আমি একটি স্বয়ংক্রিয় টেম্পোরারি ইমেইল বট।

আমার মাধ্যমে আপনি অস্থায়ী ইমেইল ঠিকানা তৈরি করতে এবং ইমেইল গ্রহণ করতে পারবেন।

/getnew কমান্ড ব্যবহার করে একটি নতুন ইমেইল ঠিকানা তৈরি করুন।
    """
    update.message.reply_text(welcome_message, parse_mode='Markdown')

# নতুন ইমেইল তৈরি করার ফাংশন
def generate_new_email(update: Update, context: CallbackContext) -> None:
    """একটি নতুন অস্থায়ী ইমেইল ঠিকানা তৈরি করে।"""
    try:
        # temp-mail লাইব্রেরি ব্যবহার করে ইমেইল তৈরি
        tm = TempMail()
        email = tm.get_email()

        if not email or "@" not in email:
            raise ValueError("API থেকে সঠিক ইমেইল পাওয়া যায়নি।")

        # ব্যবহারকারীর জন্য ইমেইল ঠিকানা ও অন্যান্য ডেটা সংরক্ষণ করা
        context.user_data['email'] = email
        context.user_data['last_checked_ids'] = set()
        context.user_data['tempmail_instance'] = tm

        keyboard = [[InlineKeyboardButton("🔄 Change Email", callback_data='change_email')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = f"✅ আপনার নতুন অস্থায়ী ইমেইল ঠিকানা:\n\n`{email}`\n\nএই ঠিকানায় কোনো ইমেইল এলে আমি আপনাকে জানিয়ে দেব।"
        
        # যদি কোনো ব্যবহারকারী বাটন থেকে কল করে, তাহলে মেসেজ এডিট হবে
        if update.callback_query:
            update.callback_query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode='Markdown')
        else: # যদি কমান্ড থেকে কল হয়
            update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

        # ব্যাকগ্রাউন্ডে ইনবক্স চেক করার জব সেট করা
        job_name = str(update.effective_chat.id)
        # পুরনো জব থাকলে রিমুভ করা
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        if current_jobs:
            for job in current_jobs:
                job.schedule_removal()
        
        context.job_queue.run_repeating(check_inbox, interval=15, first=0, context=update.effective_chat.id, name=job_name)

    except Exception as e:
        logger.error(f"Error generating new email: {e}")
        error_message = "দুঃখিত, এই মুহূর্তে নতুন ইমেইল তৈরি করা যাচ্ছে না। অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।"
        if update.callback_query:
            update.callback_query.answer(error_message, show_alert=True)
        else:
            update.message.reply_text(error_message)


# OTP এবং সার্ভিস নাম খুঁজে বের করার ফাংশন
def extract_otp_and_service(text_body):
    """ইমেইলের টেক্সট থেকে OTP এবং সার্ভিস নাম বের করে।"""
    otp, service = "N/A", "N/A"
    
    # সার্ভিস নাম খোঁজার চেষ্টা
    service_match = re.search(r'(?:The\s)?(Telegram|Google|Facebook|Twitter|Instagram|Amazon|Netflix)\sTeam', text_body, re.IGNORECASE)
    if not service_match:
        service_match = re.search(r'verify your (Telegram|Google|Facebook|Twitter|Instagram|Amazon|Netflix) account', text_body, re.IGNORECASE)
    
    if service_match:
        service = service_match.group(1).capitalize()

    # সাধারণ OTP প্যাটার্ন খোঁজা (৪ থেকে ৮ সংখ্যার কোড)
    otp_match = re.search(r'Your code is:?\s*(\d{4,8})\b|verification code:?\s*(\d{4,8})\b|\b(\d{4,8})\b is your verification code', text_body, re.IGNORECASE)
    if otp_match:
        # re.search একাধিক গ্রুপ থেকে ম্যাচ করতে পারে, তাই প্রথম যেটি পাওয়া যায় সেটি নেওয়া হচ্ছে
        otp = next((group for group in otp_match.groups() if group is not None), "N/A")

    return service, otp


# ইনবক্স চেক করার ফাংশন (ব্যাকগ্রাউন্ডে চলবে)
def check_inbox(context: CallbackContext) -> None:
    """স্বয়ংক্রিয়ভাবে নতুন ইমেইলের জন্য ইনবক্স চেক করে।"""
    chat_id = context.job.context
    user_data = context.dispatcher.user_data.get(chat_id, {})
    
    email = user_data.get('email')
    tm = user_data.get('tempmail_instance')
    
    if not email or not tm:
        return

    try:
        inbox = tm.get_inbox()

        if not isinstance(inbox, list):
            return

        last_checked_ids = user_data.get('last_checked_ids', set())
        
        for mail in inbox:
            # লাইব্রেরি থেকে mail_id বা ইউনিক কিছু পাওয়া গেলে সেটা ব্যবহার করা ভালো
            # এখানে আমরা subject এবং from দিয়ে একটি ইউনিক আইডি তৈরি করছি
            mail_unique_id = f"{mail['from']}_{mail['subject']}"
            
            if mail_unique_id not in last_checked_ids:
                # মেসেজ ফরম্যাট করা
                full_message_body = mail.get('body_text', 'No content')
                service, otp = extract_otp_and_service(full_message_body)
                
                # আপনার দেওয়া ফরম্যাট অনুযায়ী মেসেজ তৈরি
                formatted_message = f"""
*New Email Received* 📬

🕰 *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✉️ *Email:* {email}
📱 *Service:* {service}
🔑 *OTP:* `{otp}` 👈 (Tap to copy)

---
✉️ *Full Message:*
{full_message_body}
                """
                context.bot.send_message(chat_id=chat_id, text=formatted_message, parse_mode='Markdown')
                last_checked_ids.add(mail_unique_id)
        
        user_data['last_checked_ids'] = last_checked_ids

    except Exception as e:
        logger.error(f"Could not check inbox for {email}: {e}")

def main() -> None:
    """বটটি চালু করে।"""
    # আপনার বটের টোকেন এখানে দিন
    updater = Updater("8064236020:AAGS_PO-PcQAu8dCcoJMTRjQzBMtJ8TlR4g")

    dispatcher = updater.dispatcher

    # কমান্ড হ্যান্ডলার যোগ করা
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("getnew", generate_new_email))
    
    # বাটন ক্লিকের জন্য কলব্যাক হ্যান্ডলার
    dispatcher.add_handler(CallbackQueryHandler(generate_new_email, pattern='^change_email$'))

    # বট চালু করা
    updater.start_polling()
    logger.info("Bot has started.")

    updater.idle()

if __name__ == '__main__':
    main()
