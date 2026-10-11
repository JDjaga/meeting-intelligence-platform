"""Central configuration. Secrets come from the single `.env` file (git-ignored)."""
from __future__ import annotations
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # one private file for all keys — safe to hide from GitHub

DATA_DIR = BASE_DIR / "data"
DB_PATH = os.getenv("MIP_DB_PATH", str(DATA_DIR / "meetings.db"))
UPLOAD_DIR = DATA_DIR / "uploads"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("MIP_GEMINI_MODEL", "gemini-2.0-flash").strip()
GEMINI_FALLBACK_MODEL = os.getenv("MIP_GEMINI_FALLBACK", "gemini-1.5-flash").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL = os.getenv("MIP_HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
CHAT_BACKEND = os.getenv("MIP_CHAT_BACKEND", "auto")  # auto | gemini | hf
LLM_PROVIDER = os.getenv("MIP_PROVIDER", "auto")  # auto | gemini | rules

REVIEW_THRESHOLD = float(os.getenv("MIP_REVIEW_THRESHOLD", "0.60"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
