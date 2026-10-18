import os
import logging
import sqlite3
import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import google.generativeai as genai

# Import our custom tools & modules
from agent_tools import save_note, read_notes, search_web, set_reminder
from news_collector import collect_top_20_ai_news, collect_hackathons_and_competitions, get_current_date_str
from news_summarizer import get_or_create_news_summary

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

system_instruction = """
তুমি একজন স্মার্ট 24/7 পার্সোনাল এআই এজেন্ট। তুমি বাংলায় কথা বলবে।
তোমার কাছে ৪টি প্রধান টুল আছে:
১. search_web: যখন রিয়েল টাইম তথ্য, নিউজ বা আবহাওয়া জানতে চাইবে।
২. save_note / read_notes: ইউজারের কোনো তথ্য ডাটাবেসে সেভ করতে এবং পড়তে।
৩. set_reminder: ইউজার যদি কোনো কিছু মনে করিয়ে দিতে বলে, তখন তুমি set_reminder টুলটি ব্যবহার করে রিমাইন্ডার সেট করবে।
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

# In-memory selection cache: {user_id: set([news_id_1, news_id_2])}
USER_SELECTIONS = {}

# ==========================================
# TELEGRAM HANDLERS
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID: return
    await update.message.reply_text(
        "👋 হ্যালো! আমি আপনার 24/7 এআই ইন্টেলিজেন্স এজেন্ট।\n\n"
        "✨ **আমার ক্ষমতা:**\n"
        "• প্রতিদিন সকাল ৮:০০ টায় শীর্ষ ২০টি গ্লোবাল এআই ও ওপেন-সোর্স নিউজ ডেলিভারি।\n"
        "• বাংলাদেশ ও গ্লোবাল রিমোট এআই হ্যাকাথন ও প্রতিযোগিতার ট্র্যাকার।\n"
        "• একাধিক নিউজ টিক দিয়ে এক ক্লিকে ১০-১৫ লাইনের গভীর বাংলা সামারি।\n"
        "• পার্সোনাল নোট সংরক্ষণ ও স্মার্ট রিমাইন্ডার সিস্টেম।\n\n"
        "💡 *টিপ:* যেকোনো সময় আজকের নিউজ দেখতে `/news` টাইপ করুন।"
    )

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

# ==========================================
# NEWS DIGEST & INTERACTIVE CHECKBOX UI
# ==========================================

def build_news_keyboard(user_id: int, news_items: list) -> InlineKeyboardMarkup:
    """Builds the 20-headline checkbox keyboard with a dynamic submit button."""
    selected_ids = USER_SELECTIONS.get(user_id, set())
    keyboard = []
    
    for idx, item in enumerate(news_items, start=1):
        nid = item["id"]
        is_selected = nid in selected_ids
        checkbox = "✅" if is_selected else "⬜"
        title_bn = item.get('title_bn') or item['title']
        clean_title = title_bn.replace("[Paper/Model] ", "").strip()
        btn_text = f"{checkbox} {idx}. {clean_title[:30]}..." if len(clean_title) > 30 else f"{checkbox} {idx}. {clean_title}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"toggle:{nid}")])
        
    count = len(selected_ids)
    submit_text = f"🚀 নির্বাচিত নিউজের বিস্তারিত সামারি দাও ({count}টি)" if count > 0 else "🚀 নির্বাচিত নিউজের বিস্তারিত সামারি দাও (০টি সিলেক্টেড)"
    keyboard.append([InlineKeyboardButton(submit_text, callback_data="submit_news")])
    
    return InlineKeyboardMarkup(keyboard)

import asyncio
import html

async def safe_send_message(bot, chat_id: int, text: str, reply_markup=None, disable_web_page_preview=False):
    """Safely sends a message using HTML mode with automatic plain-text fallback."""
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=disable_web_page_preview
        )
    except Exception as e:
        logger.warning(f"Telegram HTML send failed ({e}), sending plain text...")
        clean_text = text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
        return await bot.send_message(
            chat_id=chat_id,
            text=clean_text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )

async def send_daily_news_digest(bot, chat_id: int):
    """
    Core function that collects Top 20 Global AI News and BD/Global Remote Hackathons,
    then dispatches separate, beautifully formatted messages with Bengali titles and short summaries.
    """
    logger.info("Starting Daily AI News & Hackathons Digest dispatch...")
    loop = asyncio.get_running_loop()
    
    # 1. Collect Top 20 Global AI News in background thread
    news_items = await loop.run_in_executor(None, collect_top_20_ai_news)
    today_str = get_current_date_str()
    
    # Reset user selection for the new day
    USER_SELECTIONS[chat_id] = set()
    
    if not news_items:
        await bot.send_message(chat_id=chat_id, text="⚠️ আজকের এআই নিউজগুলো সংগ্রহ করতে সমস্যা হয়েছে। অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।")
        return

    # Build clear Bengali news digest with 1-2 line explanations
    header = (
        f"🌅 <b>আজকের শীর্ষ ২০টি এআই ও ওপেন-সোর্স আপডেট</b>\n"
        f"📅 <i>তারিখ: {today_str}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    news_body = ""
    for idx, item in enumerate(news_items, start=1):
        t_bn = html.escape(item.get('title_bn') or item['title'])
        s_bn = html.escape(item.get('short_summary_bn') or '')
        news_body += f"📌 <b>{idx}. {t_bn}</b>\n"
        if s_bn:
            news_body += f"💡 <i>{s_bn}</i>\n\n"
        else:
            news_body += "\n"
            
    footer = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 <b>যে যে নিউজের ১০-১৫ লাইনের গভীর বাংলা সামারি পড়তে চান, নিচের বাটনে টিক (✅) দিয়ে সাবমিট বাটনে চাপ দিন:</b>"
    )
    
    markup = build_news_keyboard(chat_id, news_items)
    
    # Check if total length exceeds Telegram 4096 limit
    full_message = header + news_body + footer
    if len(full_message) <= 4000:
        await safe_send_message(bot, chat_id=chat_id, text=full_message, reply_markup=markup)
    else:
        # Split into two parts if long
        half = len(news_items) // 2
        part1_items = news_items[:half]
        part2_items = news_items[half:]
        
        part1_text = header
        for idx, item in enumerate(part1_items, start=1):
            t_bn = html.escape(item.get('title_bn') or item['title'])
            s_bn = html.escape(item.get('short_summary_bn') or '')
            part1_text += f"📌 <b>{idx}. {t_bn}</b>\n💡 <i>{s_bn}</i>\n\n"
            
        part2_text = (
            f"📅 <i>শীর্ষ এআই আপডেট (পর্ব ২):</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for idx, item in enumerate(part2_items, start=half+1):
            t_bn = html.escape(item.get('title_bn') or item['title'])
            s_bn = html.escape(item.get('short_summary_bn') or '')
            part2_text += f"📌 <b>{idx}. {t_bn}</b>\n💡 <i>{s_bn}</i>\n\n"
        part2_text += footer
        
        await safe_send_message(bot, chat_id=chat_id, text=part1_text)
        await safe_send_message(bot, chat_id=chat_id, text=part2_text, reply_markup=markup)
    
    # 2. Collect & Send BD & Global Remote Hackathons/Competitions in background thread
    events = await loop.run_in_executor(None, collect_hackathons_and_competitions)
    
    if events:
        events_text = (
            f"🏆 <b>চলমান এআই হ্যাকাথন ও প্রতিযোগিতা (বাংলাদেশ ও গ্লোবাল রিমোট)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>বাংলাদেশ থেকে ঘরে বসে অনলাইনে অথবা সরাসরি অংশ নেওয়ার শীর্ষ সুযোগসমূহ:</i>\n\n"
        )
        
        for idx, ev in enumerate(events, start=1):
            name_escaped = html.escape(ev['name'])
            org_escaped = html.escape(ev['organizer'])
            loc_escaped = html.escape(ev['location_type'])
            prize_escaped = html.escape(ev['prize_pool'])
            deadline_escaped = html.escape(ev['deadline'])
            
            events_text += (
                f"🎯 <b>{idx}. {name_escaped}</b>\n"
                f"   🏢 <b>আয়োজক:</b> {org_escaped}\n"
                f"   📍 <b>ধরন:</b> {loc_escaped}\n"
                f"   💰 <b>পুরস্কার:</b> {prize_escaped}\n"
                f"   ⏰ <b>ডেডলাইন:</b> {deadline_escaped}\n"
                f"   👉 <a href=\"{ev['url']}\">অংশগ্রহণ / রেজিস্ট্রেশন লিংক</a>\n\n"
            )
            
        await safe_send_message(bot, chat_id=chat_id, text=events_text, disable_web_page_preview=True)
        
    logger.info("Daily digest dispatched successfully.")

async def handle_news_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles real-time toggling of news checkboxes (⬜ <-> ✅).
    Directly updates existing keyboard state without depending on database queries.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if not data.startswith("toggle:"):
        return
        
    news_id = int(data.split(":")[1])
    
    if user_id not in USER_SELECTIONS:
        USER_SELECTIONS[user_id] = set()
        
    if news_id in USER_SELECTIONS[user_id]:
        USER_SELECTIONS[user_id].remove(news_id)
    else:
        USER_SELECTIONS[user_id].add(news_id)
        
    current_markup = query.message.reply_markup
    if not current_markup:
        return
        
    new_keyboard = []
    selected_set = USER_SELECTIONS[user_id]
    
    for row in current_markup.inline_keyboard:
        new_row = []
        for btn in row:
            if btn.callback_data.startswith("toggle:"):
                btn_nid = int(btn.callback_data.split(":")[1])
                is_sel = btn_nid in selected_set
                text = btn.text
                if is_sel and text.startswith("⬜"):
                    text = "✅" + text[1:]
                elif not is_sel and text.startswith("✅"):
                    text = "⬜" + text[1:]
                new_row.append(InlineKeyboardButton(text=text, callback_data=btn.callback_data))
            elif btn.callback_data == "submit_news":
                count = len(selected_set)
                submit_text = f"🚀 নির্বাচিত নিউজের বিস্তারিত সামারি দাও ({count}টি)" if count > 0 else "🚀 নির্বাচিত নিউজের বিস্তারিত সামারি দাও (০টি সিলেক্টেড)"
                new_row.append(InlineKeyboardButton(text=submit_text, callback_data="submit_news"))
            else:
                new_row.append(btn)
        new_keyboard.append(new_row)
        
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
    except Exception as e:
        logger.warning(f"Error editing reply markup: {e}")

async def handle_news_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the submission of selected news items and dispatches 10-15 line summaries."""
    query = update.callback_query
    user_id = update.effective_user.id
    selected_ids = list(USER_SELECTIONS.get(user_id, set()))
    
    if not selected_ids:
        await query.answer("⚠️ অনুগ্রহ করে প্রথমে অন্তত ১টি নিউজের টিকমার্কে ক্লিক করুন!", show_alert=True)
        return
        
    await query.answer(f"✅ {len(selected_ids)}টি নিউজের সামারি তৈরি হচ্ছে...")
    
    await context.bot.send_message(
        chat_id=user_id,
        text=f"⏳ আপনার নির্বাচিত <b>{len(selected_ids)}টি</b> নিউজের ১০-১৫ লাইনের গভীর বাংলা সামারি তৈরি হচ্ছে, দয়া করে একটু অপেক্ষা করুন...",
        parse_mode="HTML"
    )
    
    loop = asyncio.get_running_loop()
    for idx, nid in enumerate(selected_ids, start=1):
        res = await loop.run_in_executor(None, get_or_create_news_summary, nid)
        title = res.get("title", "নিউজ শিরোনাম")
        summary = res.get("summary", "সামারি পাওয়া যায়নি।")
        url = res.get("url", "")
        
        msg = (
            f"📰 <b>[{idx}/{len(selected_ids)}] {html.escape(title)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{html.escape(summary)}"
        )
        
        reply_markup = None
        if url:
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 মূল ওয়েবসাইট / রিসার্চ পেপার পড়ুন", url=url)]
            ])
            
        await safe_send_message(
            context.bot,
            chat_id=user_id,
            text=msg,
            reply_markup=reply_markup
        )
        
    # Clear user selection after dispatch
    USER_SELECTIONS[user_id] = set()

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual trigger command `/news` for testing and on-demand digest."""
    if update.effective_user.id != ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt by {update.effective_user.id}")
        return
        
    try:
        status_msg = await update.message.reply_text("🔎 আজকের টপ ২০টি এআই নিউজ ও হ্যাকাথন সংগ্রহ করছি... অনুগ্রহ করে কয়েক সেকেন্ড অপেক্ষা করুন।")
        await send_daily_news_digest(context.bot, update.effective_chat.id)
        try:
            await status_msg.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error in news_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ নিউজ লোড করতে সাময়িক সমস্যা হয়েছে: {e}")

# ==========================================
# BACKGROUND SCHEDULERS
# ==========================================

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Background Job: Checks database for pending reminders."""
    try:
        conn = sqlite3.connect("memory.db")
        cursor = conn.cursor()
        now = datetime.datetime.now()
        
        cursor.execute("SELECT id, message FROM reminders WHERE is_sent=0 AND remind_at <= ?", (now,))
        due_reminders = cursor.fetchall()
        
        for row in due_reminders:
            rem_id, msg = row
            await context.bot.send_message(chat_id=ALLOWED_USER_ID, text=f"⏰ **রিমাইন্ডার:**\n{msg}")
            cursor.execute("UPDATE reminders SET is_sent=1 WHERE id=?", (rem_id,))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Reminder System Error: {e}")

async def scheduled_daily_news_job(context: ContextTypes.DEFAULT_TYPE):
    """Daily 08:00 AM BST Job for sending news."""
    try:
        await send_daily_news_digest(context.bot, ALLOWED_USER_ID)
    except Exception as e:
        logger.error(f"Daily News Scheduled Job Error: {e}")

# ==========================================
# CLOUD HEALTH SERVER
# ==========================================

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"OK"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "2")
        self.send_header("Connection", "close")
        self.end_headers()

    def log_message(self, format, *args):
        pass # Suppress noisy healthcheck logs
        
def run_dummy_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def main() -> None:
    # 1. Start dummy server for Cloud Health Checks
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # 2. Build Telegram Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # 3. Add Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CallbackQueryHandler(handle_news_toggle, pattern=r"^toggle:\d+$"))
    application.add_handler(CallbackQueryHandler(handle_news_submit, pattern=r"^submit_news$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 4. Job Queue: Reminders every 30 seconds
    application.job_queue.run_repeating(check_reminders, interval=30, first=10)
    
    # 5. Job Queue: Daily 08:00 AM (Asia/Dhaka) News Digest
    try:
        dhaka_tz = ZoneInfo("Asia/Dhaka")
    except Exception:
        dhaka_tz = datetime.timezone(datetime.timedelta(hours=6))
        
    daily_time = datetime.time(hour=8, minute=0, tzinfo=dhaka_tz)
    application.job_queue.run_daily(scheduled_daily_news_job, time=daily_time)
    
    logger.info(f"✅ 24/7 Agent is online with Daily AI News scheduled at {daily_time} (Asia/Dhaka)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
