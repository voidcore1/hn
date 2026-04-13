import os
import sys
from dotenv import load_dotenv
from groq import Groq

# load variables from .env file (if present) into os.environ
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY not set. Create a .env file with your key.")
    print("   See .env.example for the format.")
    sys.exit(1)

client = Groq(api_key=GROQ_API_KEY)

# models to try in order (fallback chain)
MODELS = [
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant",
]
