"""Central configuration: paths, API keys, settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
# config.py lives at src/gocam/config.py
# Going up two levels gives the project root (gocam-curator/).
_PACKAGE_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = _PACKAGE_DIR.parent.parent

PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
PROCESSES_DIR: Path = PROJECT_ROOT / "processes"
SEARCHES_DIR: Path = PROJECT_ROOT / "searches"  # global search results (all processes)

# ---------------------------------------------------------------------------
# LLM provider selection
# ---------------------------------------------------------------------------
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" | "gemini" | "vertex"

# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

# ---------------------------------------------------------------------------
# Vertex AI settings (used when LLM_PROVIDER=vertex)
# ---------------------------------------------------------------------------
VERTEX_PROJECT: str | None = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT")
VERTEX_LOCATION: str = os.getenv("VERTEX_LOCATION", "us-central1")

# ---------------------------------------------------------------------------
# Model IDs (override via env if needed)
# ---------------------------------------------------------------------------
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

# Comma-separated fallback models for Gemini when quota is exhausted.
# Tried in order after the primary model fails and a cooldown wait doesn't help.
GEMINI_FALLBACK_MODELS: list[str] = [
    m.strip()
    for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.0-flash").split(",")
    if m.strip()
]

# ---------------------------------------------------------------------------
# Per-provider inter-call delays (seconds between consecutive API calls)
# API_CALL_DELAY sets both; provider-specific vars override it.
# ---------------------------------------------------------------------------
_global_delay = os.getenv("API_CALL_DELAY", "")
ANTHROPIC_API_CALL_DELAY: int = int(os.getenv("ANTHROPIC_API_CALL_DELAY", _global_delay or "2"))
GEMINI_API_CALL_DELAY: int = int(os.getenv("GEMINI_API_CALL_DELAY", _global_delay or "10"))
VERTEX_API_CALL_DELAY: int = int(os.getenv("VERTEX_API_CALL_DELAY", _global_delay or "2"))

# ---------------------------------------------------------------------------
# Provider-specific PDF extraction defaults
# ---------------------------------------------------------------------------
# chunk_pages: pages per API call when processing PDFs.
# None = send the entire document in one call (Anthropic handles large contexts well).
# Integer = split into chunks of that many pages (Gemini has tighter output limits).
# Override with PDF_CHUNK_PAGES env var (integer or "none" for single call).
PROVIDER_DEFAULTS: dict[str, dict] = {
    "anthropic": {"chunk_pages": None, "text_chunk_chars": None},
    "gemini": {"chunk_pages": 8, "text_chunk_chars": 30_000},
    "vertex": {"chunk_pages": 8, "text_chunk_chars": 30_000},
}

# Overlap between PDF chunks (characters from the end of the previous chunk
# prepended to the next). Override with PDF_CHUNK_OVERLAP env var.
PDF_CHUNK_OVERLAP: int = int(os.getenv("PDF_CHUNK_OVERLAP", "500"))


def get_pdf_chunk_pages() -> int | None:
    """Return pages-per-chunk for the active provider (None = single call).

    The PDF_CHUNK_PAGES env var overrides the provider default.
    Set to an integer, or "none" / "0" for single-call mode.
    """
    env = os.getenv("PDF_CHUNK_PAGES", "").strip().lower()
    if env:
        if env in ("none", "0"):
            return None
        try:
            return int(env)
        except ValueError:
            pass
    return PROVIDER_DEFAULTS.get(LLM_PROVIDER, {}).get("chunk_pages", None)


def get_text_chunk_chars() -> int | None:
    """Return max characters per chunk when processing text files (None = single call).

    Gemini/Vertex default to 30 000 chars per chunk so Flash models see a
    focused section rather than an entire paper at once.
    Override with TEXT_CHUNK_CHARS env var (integer or "none" / "0").
    """
    env = os.getenv("TEXT_CHUNK_CHARS", "").strip().lower()
    if env:
        if env in ("none", "0"):
            return None
        try:
            return int(env)
        except ValueError:
            pass
    return PROVIDER_DEFAULTS.get(LLM_PROVIDER, {}).get("text_chunk_chars", None)

# ---------------------------------------------------------------------------
# Process subdirectory names
# ---------------------------------------------------------------------------
PROCESS_SUBDIRS: list[str] = [
    "input",
    "extractions",
    "validation",
    "narratives",
]
