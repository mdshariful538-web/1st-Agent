import sqlite3
import datetime
from duckduckgo_search import DDGS

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect("memory.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT)''')
    # নতুন টেবিল: রিমাইন্ডার সেভ করার জন্য
    cursor.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, message TEXT, remind_at TIMESTAMP, is_sent INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- MEMORY TOOLS ---
def save_note(title: str, content: str) -> str:
    """Saves a personal note or important information for the user."""
    try:
        conn = sqlite3.connect("memory.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (title, content) VALUES (?, ?)", (title, content))
        conn.commit()
        conn.close()
        return f"Note '{title}' saved successfully."
    except Exception as e:
        return f"Failed to save note: {e}"

def read_notes() -> str:
    """Reads and retrieves all saved personal notes of the user."""
    try:
        conn = sqlite3.connect("memory.db")
        cursor = conn.cursor()
        cursor.execute("SELECT title, content FROM notes")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return "No notes found in memory."
        return "Saved Notes:\n" + "\n".join([f"- {r[0]}: {r[1]}" for r in rows])
    except Exception as e:
        return f"Failed to read notes: {e}"

# --- WEB SEARCH TOOL ---
def search_web(query: str) -> str:
    """Searches the internet for real-time information, news, or facts."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results: return "No results found on the web."
        return "Web Search Results:\n" + "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except Exception as e:
        return f"Error performing web search: {str(e)}"

# --- SCHEDULER TOOL ---
def set_reminder(minutes_from_now: int, message: str) -> str:
    """Sets a timer to remind the user about something after a specific number of minutes."""
    try:
        remind_at = datetime.datetime.now() + datetime.timedelta(minutes=minutes_from_now)
        conn = sqlite3.connect("memory.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO reminders (message, remind_at) VALUES (?, ?)", (message, remind_at))
        conn.commit()
        conn.close()
        return f"Success! Reminder set for {minutes_from_now} minutes from now."
    except Exception as e:
        return f"Error setting reminder: {e}"
