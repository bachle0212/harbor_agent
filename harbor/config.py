"""Runtime configuration. Secrets come from the environment, never from code."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

ARTICLES_DIR = ROOT / "data" / "articles"
STATE_PATH = ROOT / "data" / "state.json"
LOG_DIR = ROOT / "logs"
LAST_RUN_PATH = LOG_DIR / "last-run.json"

HELP_CENTER_ORIGIN = "https://support.optisigns.com"
ARTICLES_API = (
    "https://support.optisigns.com/api/v2/help_center/{locale}/articles.json"
)

# Gemini File Search: 512 is the API maximum; overlap must be ≤ half of that.
CHUNK_SIZE_TOKENS = int(os.getenv("CHUNK_SIZE_TOKENS", "512"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "256"))
MIN_ARTICLES = int(os.getenv("MIN_ARTICLES", "30"))
ZENDESK_LOCALE = os.getenv("ZENDESK_LOCALE", "en-us")
# Public Help Center: pause between pages; 429 uses Retry-After on top of this.
SCRAPE_MIN_INTERVAL = float(os.getenv("SCRAPE_MIN_INTERVAL", "0.5"))
SCRAPE_MAX_RETRIES = int(os.getenv("SCRAPE_MAX_RETRIES", "5"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")

SYSTEM_PROMPT = (
    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
    "• Tone: helpful, factual, concise.\n"
    "• Only answer using the uploaded docs.\n"
    "• Max 5 bullet points; else link to the doc.\n"
    '• Cite up to 3 "Article URL:" lines per reply.'
)

STORE_ENV_KEY = "GEMINI_FILE_SEARCH_STORE"


def api_key() -> str:
    """Accept GEMINI_API_KEY, GOOGLE_API_KEY, or API_KEY (not an OpenAI sk- key)."""
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    alias = (os.getenv("API_KEY") or "").strip()
    if alias and not alias.startswith("sk-"):
        return alias
    return ""


def vector_store_id() -> str:
    value = (os.getenv(STORE_ENV_KEY) or "").strip()
    if value.startswith("vs_") or value.startswith("file-"):
        return ""
    return value


def persist_vector_store_id(store_id: str) -> None:
    """Write GEMINI_FILE_SEARCH_STORE back to .env without touching other keys."""
    path = ROOT / ".env"
    if not path.exists() or not store_id:
        return
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.startswith(f"{STORE_ENV_KEY}="):
            newline = "\n" if line.endswith("\n") else ""
            out.append(f"{STORE_ENV_KEY}={store_id}{newline}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        suffix = "" if (out and out[-1].endswith("\n")) else "\n"
        out.append(f"{suffix}{STORE_ENV_KEY}={store_id}\n")
    path.write_text("".join(out), encoding="utf-8")
    os.environ[STORE_ENV_KEY] = store_id
    load_dotenv(path, override=True)
