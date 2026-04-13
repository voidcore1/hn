import os
import sys
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY not set. Copy .env.example to .env and add your key.")
    sys.exit(1)

client = Groq(api_key=GROQ_API_KEY)

# fallback chain — if one model is rate-limited, try the next
MODELS = [
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant",
]
