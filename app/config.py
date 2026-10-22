import os
from dotenv import load_dotenv

load_dotenv()

API_PROVIDER = os.getenv("API_PROVIDER", "openrouter")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

# Ollama (local)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b")

NSFW_BLOCK_THRESHOLD = float(os.getenv("NSFW_BLOCK_THRESHOLD", "0.95"))
NSFW_PASS_THRESHOLD = float(os.getenv("NSFW_PASS_THRESHOLD", "0.15"))
DB_PATH = os.getenv("DB_PATH", "moderation.db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
AUTO_START_WORKER = os.getenv("AUTO_START_WORKER", "false").lower() == "true"