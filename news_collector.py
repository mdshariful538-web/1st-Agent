import sqlite3
import datetime
import logging
import requests
import re
from typing import List, Dict, Any
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

DB_PATH = "memory.db"

def get_current_date_str() -> str:
    """Returns today's date in YYYY-MM-DD for Asia/Dhaka or UTC."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("Asia/Dhaka"))
    except Exception:
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    return now.strftime("%Y-%m-%d")

# ==========================================
# 1. GLOBAL AI & OPEN SOURCE NEWS COLLECTOR
# ==========================================

def fetch_hn_ai_stories(limit: int = 25) -> List[Dict[str, str]]:
    """Fetches high-signal AI and Open Source stories from Hacker News Algolia API."""
    stories = []
    # 24 hours ago timestamp
    yesterday_ts = int((datetime.datetime.utcnow() - datetime.timedelta(days=1)).timestamp())
    queries = ["AI", "LLM", "Open Source model", "artificial intelligence"]
    
    headers = {"User-Agent": "1st-Agent-Bot/1.0"}
    
    for q in queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&numericFilters=created_at_i>{yesterday_ts}&hitsPerPage={limit}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for hit in data.get("hits", []):
                    title = hit.get("title", "")
                    story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                    points = hit.get("points") or 0
                    
                    # Filter for relevance
                    ai_keywords = ["ai", "llm", "model", "gpt", "gemini", "llama", "deepseek", "claude", "open source", "weights", "agent", "transformer", "neural"]
                    if any(k in title.lower() for k in ai_keywords):
                        stories.append({
                            "title": title.strip(),
                            "url": story_url.strip(),
                            "source": "Hacker News / Tech",
                            "score": points
                        })
        except Exception as e:
            logger.warning(f"Error fetching HN AI stories for query '{q}': {e}")
            
    return stories

def fetch_huggingface_daily_papers() -> List[Dict[str, str]]:
    """Fetches trending AI research papers & open source models from Hugging Face."""
    papers = []
    try:
        headers = {"User-Agent": "1st-Agent-Bot/1.0"}
        # HF daily papers API
        resp = requests.get("https://huggingface.co/api/daily_papers", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data[:15]:
                paper = item.get("paper", {})
                title = paper.get("title", "")
                paper_id = paper.get("id", "")
                summary = paper.get("summary", "")
                upvotes = item.get("paper", {}).get("upvotes", 0)
                if title and paper_id:
                    papers.append({
                        "title": f"[Paper/Model] {title.strip()}",
                        "url": f"https://huggingface.co/papers/{paper_id}",
                        "source": "Hugging Face Daily Papers",
                        "score": upvotes + 10  # Weight upvotes
                    })
    except Exception as e:
        logger.warning(f"Error fetching Hugging Face daily papers: {e}")
    return papers

def fetch_ddg_ai_news() -> List[Dict[str, str]]:
    """Searches DuckDuckGo for top breaking AI news and open source releases."""
    results = []
    queries = [
        "artificial intelligence breakthrough news",
        "open source AI model released 2026",
        "LLM update OpenAI Google Anthropic Meta"
    ]
    for q in queries:
        try:
            with DDGS() as ddgs:
                items = list(ddgs.news(q, max_results=8))
                for item in items:
                    title = item.get("title", "")
                    link = item.get("url", "")
                    source = item.get("source", "Web News")
                    if title and link:
                        results.append({
                            "title": title.strip(),
                            "url": link.strip(),
                            "source": source,
                            "score": 5
                        })
        except Exception as e:
            logger.warning(f"Error fetching DDG news for '{q}': {e}")
    return results

def collect_top_20_ai_news() -> List[Dict[str, Any]]:
    """Gathers, deduplicates, ranks, and saves the Top 20 Global AI News."""
    all_candidates = []
    all_candidates.extend(fetch_huggingface_daily_papers())
    all_candidates.extend(fetch_hn_ai_stories(limit=30))
    all_candidates.extend(fetch_ddg_ai_news())
    
    # Deduplicate by URL and similar Title
    seen_urls = set()
    unique_stories = []
    
    for item in sorted(all_candidates, key=lambda x: x.get("score", 0), reverse=True):
        url = item.get("url", "")
        title = item.get("title", "")
        # Normalize
        norm_url = re.sub(r'https?://(www\.)?', '', url).split('?')[0].rstrip('/')
        if norm_url in seen_urls:
            continue
        seen_urls.add(norm_url)
        unique_stories.append(item)
        
    top_20 = unique_stories[:20]
    
    # Save to SQLite Database
    today_str = get_current_date_str()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    saved_items = []
    for item in top_20:
        title = item["title"]
        url = item["url"]
        source = item["source"]
        try:
            cursor.execute("""
                INSERT INTO daily_news (publish_date, category, title, source_name, url)
                VALUES (?, 'GLOBAL_AI', ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET title=excluded.title
            """, (today_str, title, source, url))
            conn.commit()
        except Exception as e:
            logger.error(f"Error storing news item: {e}")
            
    # Retrieve saved IDs
    cursor.execute("""
        SELECT id, title, source_name, url 
        FROM daily_news 
        WHERE publish_date = ? AND category = 'GLOBAL_AI'
        ORDER BY id ASC LIMIT 20
    """, (today_str,))
    rows = cursor.fetchall()
    conn.close()
    
    for r in rows:
        saved_items.append({
            "id": r[0],
            "title": r[1],
            "source": r[2],
            "url": r[3]
        })
        
    return saved_items

# ========================================================
# 2. BANGLADESH & GLOBAL REMOTE HACKATHONS / COMPETITIONS
# ========================================================

def collect_hackathons_and_competitions() -> List[Dict[str, Any]]:
    """
    Collects upcoming & active AI hackathons and competitions:
    - Online/Global Remote (Devpost, Lablab.ai, Kaggle) accessible from BD
    - In-Person / Hybrid in Bangladesh (University fests, National Olympiads)
    """
    events = []
    
    # 1. Search Global Online / Remote Hackathons via DuckDuckGo
    online_queries = [
        "site:devpost.com hackathons AI online open",
        "site:lablab.ai hackathon open",
        "kaggle AI machine learning active competitions"
    ]
    
    for q in online_queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(q, max_results=5))
                for res in results:
                    title = res.get("title", "")
                    link = res.get("href", "")
                    body = res.get("body", "")
                    
                    if "hackathon" in title.lower() or "competition" in title.lower() or "challenge" in title.lower():
                        organizer = "Devpost / Global Platform"
                        if "lablab" in link: organizer = "Lablab.ai"
                        elif "kaggle" in link: organizer = "Kaggle"
                        
                        events.append({
                            "name": title.split('|')[0].split('-')[0].strip(),
                            "organizer": organizer,
                            "location_type": "🌐 অনলাইন (বাংলাদেশ থেকে অংশগ্রহণযোগ্য)",
                            "prize_pool": "ক্যাশ প্রাইজ / ক্রেডেনশিয়াল ও স্বাগ",
                            "deadline": "চলমান / উন্মুক্ত",
                            "url": link
                        })
        except Exception as e:
            logger.warning(f"Error querying online hackathons: {e}")

    # 2. Search Bangladesh Local / National AI Events
    bd_queries = [
        "Bangladesh AI hackathon competition 2026",
        "BUET CSE fest hackathon 2026",
        "National AI Olympiad or Contest Bangladesh"
    ]
    
    for q in bd_queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(q, max_results=4))
                for res in results:
                    title = res.get("title", "")
                    link = res.get("href", "")
                    if any(w in title.lower() for w in ["hackathon", "competition", "contest", "fest", "olympiad"]):
                        events.append({
                            "name": title.split('|')[0].strip(),
                            "organizer": "বাংলাদেশ টেক কমিউনিটি / বিশ্ববিদ্যালয়",
                            "location_type": "🇧🇩 বাংলাদেশ (অনলাইন / অন-সাইট)",
                            "prize_pool": "প্রাইজমানি ও সার্টিফিকেট",
                            "deadline": "রেজিস্ট্রেশন চলছে",
                            "url": link
                        })
        except Exception as e:
            logger.warning(f"Error querying BD hackathons: {e}")

    # Deduplicate events by URL
    seen_urls = set()
    unique_events = []
    for ev in events:
        norm_url = ev["url"].split('?')[0].rstrip('/')
        if norm_url not in seen_urls and len(ev["name"]) > 5:
            seen_urls.add(norm_url)
            unique_events.append(ev)

    # Fallback to high-value staple platforms if web search was sparse
    if len(unique_events) < 3:
        unique_events.extend([
            {
                "name": "Kaggle Community AI & ML Competitions",
                "organizer": "Kaggle / Google",
                "location_type": "🌐 অনলাইন (সবার জন্য উন্মুক্ত)",
                "prize_pool": "$১০,০০০ - $১০০,০০০+",
                "deadline": "চলমান (যেকোনো সময় জয়েন করুন)",
                "url": "https://www.kaggle.com/competitions"
            },
            {
                "name": "Lablab.ai Autonomous AI Agent Hackathons",
                "organizer": "Lablab.ai Global",
                "location_type": "🌐 অনলাইন (রিমোট হ্যাকাথন)",
                "prize_pool": "ক্যাশ প্রাইজ ও ইনকিউবেশন গ্রান্ট",
                "deadline": "সাপ্তাহিক ও মাসিক ভিত্তিতে চালু",
                "url": "https://lablab.ai/event"
            },
            {
                "name": "Devpost Global Generative AI Hackathons",
                "organizer": "Devpost Platform",
                "location_type": "🌐 অনলাইন (বাংলাদেশ থেকে ঘরে বসে অংশগ্রহণযোগ্য)",
                "prize_pool": "$২৫,০০০ - $৫০,০০০+",
                "deadline": "প্রতি সপ্তাহে নতুন হ্যাকাথন",
                "url": "https://devpost.com/hackathons"
            }
        ])

    curated_events = unique_events[:6]

    # Save to SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved_events = []
    for ev in curated_events:
        try:
            cursor.execute("""
                INSERT INTO daily_events (event_name, organizer, location_type, prize_pool, deadline, url)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET event_name=excluded.event_name, deadline=excluded.deadline
            """, (ev["name"], ev["organizer"], ev["location_type"], ev["prize_pool"], ev["deadline"], ev["url"]))
            conn.commit()
            saved_events.append(ev)
        except Exception as e:
            logger.error(f"Error storing event: {e}")
    conn.close()

    return saved_events
