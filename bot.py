import os
import logging
import sqlite3
import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Import our custom tools
from agent_tools import save_note, read_notes, search_web, set_reminder

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

system_instruction = """
তুমি একজন স্মার্ট 24/7 পার্সোনাল এআই এজেন্ট। তুমি বাংলায় কথা বলবে।
তোমার কাছে ৩টি প্রধান টুল আছে:
১. search_web: যখন রিয়েল টাইম তথ্য, নিউজ বা আবহাওয়া জানতে চাইবে।
২. save_note / read_notes: ইউজারের কোনো তথ্য ডাটাবেসে সেভ করতে এবং পড়তে।
৩. set_reminder: ইউজার যদি কোনো কিছু মনে করিয়ে দিতে বলে (যেমন: "আমাকে ১০ মিনিট পর মিটিংয়ের কথা মনে করিয়ে দাও"), তখন তুমি set_reminder টুলটি ব্যবহার করে রিমাইন্ডার সেট করবে।
"""

# Initialize Model with Tools
model = genai.GenerativeModel(
    model_name='gemini-3.8-flash',
    system_instruction=system_instruction,
    tools=[save_note, read_notes, search_web, set_reminder]
)

chat_session = model.start_chat(enable_automatic_function_calling=True)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID: return
    await update.message.reply_text("হ্যালো! আমি আপনার 24/7 এআই এজেন্ট। আমি এখন ওয়েব সার্চ ও মেমোরির পাশাপাশি আপনার জন্য **রিমাইন্ডার** সেট করতে পারি! ⏰")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID: return
    
    user_text = update.message.text
    status_msg = await update.message.reply_text("⏳ কাজ করছি...")

    import asyncio
    loop = asyncio.get_running_loop()
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            response = await loop.run_in_executor(None, chat_session.send_message, user_text)
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text=response.text)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Gemini API error (attempt {attempt+1}): {e}. Retrying...")
                await asyncio.sleep(2)
            else:
                logger.error(f"Final Error: {e}")
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text="❌ গুগলের সার্ভার কানেকশন ড্রপ করেছে (504 Timeout)। দয়া করে কিছুক্ষণ পর আবার ট্রাই করুন।")

# Background Job: Checks database for pending reminders
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect("memory.db")
        cursor = conn.cursor()
        now = datetime.datetime.now()
        
        # Find reminders where time has passed and not yet sent
        cursor.execute("SELECT id, message FROM reminders WHERE is_sent=0 AND remind_at <= ?", (now,))
        due_reminders = cursor.fetchall()
        
        for row in due_reminders:
            rem_id, msg = row
            # Send the reminder to the user
            await context.bot.send_message(chat_id=ALLOWED_USER_ID, text=f"⏰ **রিমাইন্ডার:**\n{msg}")
            # Mark as sent
            cursor.execute("UPDATE reminders SET is_sent=1 WHERE id=?", (rem_id,))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Reminder System Error: {e}")

def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run the reminder checker every 30 seconds in the background
    application.job_queue.run_repeating(check_reminders, interval=30, first=10)
    
    logger.info("✅ 24/7 Agent is online with Scheduler...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
