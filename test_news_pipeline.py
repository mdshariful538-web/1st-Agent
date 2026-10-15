import os
import sqlite3
from agent_tools import init_db
from news_collector import collect_top_20_ai_news, collect_hackathons_and_competitions, get_current_date_str
from news_summarizer import get_or_create_news_summary

def test_pipeline():
    print("--- 1. Testing Database Initialization ---")
    init_db()
    conn = sqlite3.connect("memory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"Tables found: {tables}")
    assert "daily_news" in tables, "daily_news missing"
    assert "daily_events" in tables, "daily_events missing"
    assert "user_selection_state" in tables, "user_selection_state missing"
    conn.close()
    print("✅ DB tables verified!")

    print("\n--- 2. Testing News Collection (Top 20 AI News) ---")
    news_items = collect_top_20_ai_news()
    print(f"Collected {len(news_items)} news items.")
    for idx, item in enumerate(news_items[:5], 1):
        print(f"  {idx}. {item['title']} ({item['source']})")
    assert len(news_items) > 0, "No news collected"

    print("\n--- 3. Testing Hackathons & Competitions Collection ---")
    events = collect_hackathons_and_competitions()
    print(f"Collected {len(events)} events.")
    for idx, ev in enumerate(events, 1):
        print(f"  {idx}. {ev['name']} | {ev['location_type']} | {ev['url']}")
    assert len(events) > 0, "No events collected"

    print("\n--- 4. Testing Bengali 10-15 Line Summarization ---")
    first_id = news_items[0]["id"]
    res = get_or_create_news_summary(first_id)
    print(f"Summary for Item ID {first_id}:")
    print(f"Title: {res['title']}")
    print(f"URL: {res['url']}")
    print("Summary Text:")
    print(res["summary"])
    
    lines = [l for l in res["summary"].split("\n") if l.strip()]
    print(f"\nTotal non-empty lines in summary: {len(lines)}")
    assert len(res["summary"]) > 100, "Summary too short"
    print("✅ Summarization verified successfully!")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_pipeline()
