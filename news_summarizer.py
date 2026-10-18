import os
import sqlite3
import logging
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

DB_PATH = "memory.db"

# Model for summarization
summary_model = genai.GenerativeModel(model_name="gemini-3.8-flash")

def extract_webpage_content(url: str) -> str:
    """
    Extracts readable article text from a given URL.
    Uses BeautifulSoup primary parsing, with Jina Reader as fallback.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    extracted_text = ""
    
    # Attempt 1: Direct requests + BeautifulSoup
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove junk tags
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
                tag.decompose()
            
            # Look for article or main tags
            article_tag = soup.find("article") or soup.find("main") or soup.find("div", class_=lambda x: x and "content" in x)
            target = article_tag if article_tag else soup.body
            
            if target:
                paragraphs = target.find_all("p")
                text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
                if len(text) > 200:
                    extracted_text = text[:8000]
    except Exception as e:
        logger.warning(f"Direct text extraction failed for {url}: {e}")

    # Attempt 2: Jina AI Reader Fallback (clean markdown extractor for AI)
    if len(extracted_text) < 200:
        try:
            jina_url = f"https://r.jina.ai/{url}"
            resp = requests.get(jina_url, headers={"User-Agent": "1st-Agent-Bot/1.0"}, timeout=15)
            if resp.status_code == 200 and len(resp.text) > 100:
                extracted_text = resp.text[:8000]
        except Exception as e:
            logger.warning(f"Jina extraction failed for {url}: {e}")

    return extracted_text

def generate_bengali_summary(title: str, url: str, content: str) -> str:
    """
    Generates a high-quality, structured 10 to 15 lines summary in natural Bengali.
    """
    if not content or len(content.strip()) < 50:
        content = f"Article Title: {title}. Source Link: {url}"

    prompt = f"""
তুমি একজন অত্যন্ত অভিজ্ঞ সিনিয়র এআই রিসার্চার ও টেকনোলজি স্পেশালিস্ট।
নিচে একটি সাম্প্রতিক এআই বা ওপেন-সোর্স নিউজের তথ্য দেওয়া হলো। তোমার দায়িত্ব হলো এই নিউজটি পড়ে বাংলা ভাষায় একটি সহজবোধ্য, তথ্যবহুল ও গভীর সামারি তৈরি করা।

শিরোনাম: {title}
সোর্স লিংক: {url}
কনটেন্ট:
{content}

**কড়া নিয়মাবলী:**
১. সামারিটি স্পষ্টভাবে ঠিক ১০ থেকে ১৫ লাইনের মধ্যে হতে হবে। (১০ লাইনের কম বা ১৫ লাইনের বেশি হওয়া যাবে না)।
২. ভাষা হতে হবে সাবলীল, পরিষ্কার এবং সাধারণ ডেভেলপার বা শিক্ষার্থীর সহজে বোঝার উপযোগী।
৩. কোনো জটিল ইংরেজি শব্দ থাকলে তা সুন্দরভাবে বাংলায় বুঝিয়ে বলবে।
৪. নিচের ৪টি পয়েন্টের সুনির্দিষ্ট কাঠামোর মধ্যে সামারিটি উপস্থাপন করবে:

📌 **মূল ঘটনা / কী রিলিজ হয়েছে:** (৩-৪ লাইন)
⚙️ **প্রযুক্তিগত বৈশিষ্ট্য ও স্পেসিফিকেশন:** (৩-৪ লাইন)
💡 **কেন এটি গুরুত্বপূর্ণ ও কাদের জন্য সহায়ক:** (৩-৪ লাইন)
🚀 **ভবিষ্যত প্রভাব ও ব্যবহারিক সুযোগ:** (২-৩ লাইন)
"""
    try:
        response = summary_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini summarization error: {e}")
        return f"❌ সামারি জেনারেট করতে সাময়িক সমস্যা হয়েছে: {e}\n\nআপনি চাইলে সরাসরি নিচের লিংকে ক্লিক করে মূল আর্টিকেলটি পড়তে পারেন।"

def get_or_create_news_summary(news_id: int) -> dict:
    """
    Retrieves the news item by ID, generates the summary if not cached,
    saves the cache in SQLite, and returns title, summary, and url.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, title_bn, url, cached_summary FROM daily_news WHERE id = ?", (news_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {"error": "নিউজটি খুঁজে পাওয়া যায়নি।"}
    
    nid, title, title_bn, url, cached_summary = row
    display_title = title_bn or title
    
    # If already cached, return immediately
    if cached_summary and len(cached_summary.strip()) > 50:
        conn.close()
        return {
            "id": nid,
            "title": display_title,
            "title_bn": display_title,
            "url": url,
            "summary": cached_summary
        }
    
    conn.close()
    
    # Otherwise fetch content and generate
    content = extract_webpage_content(url)
    summary = generate_bengali_summary(title, url, content)
    
    # Save back to database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE daily_news SET cached_summary = ? WHERE id = ?", (summary, nid))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error caching summary: {e}")
        
    return {
        "id": nid,
        "title": title,
        "url": url,
        "summary": summary
    }
