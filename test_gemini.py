import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

try:
    print("Listing models:")
    for m in genai.list_models():
        print(m.name)
except Exception as e:
    print("ERROR:", str(e))
