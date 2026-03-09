"""Central configuration: paths, API keys, settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
# config.py lives at src/gocam/config.py
# Going up two levels gives the project root (gocam-curator/).
_PACKAGE_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = _PACKAGE_DIR.parent.parent

PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
PROCESSES_DIR: Path = PROJECT_ROOT / "processes"

# ---------------------------------------------------------------------------
# LLM provider selection
# ---------------------------------------------------------------------------
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" | "gemini"

# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

# ---------------------------------------------------------------------------
# Model IDs (override via env if needed)
# ---------------------------------------------------------------------------
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

# ---------------------------------------------------------------------------
# Per-provider inter-call delays (seconds between consecutive API calls)
# API_CALL_DELAY sets both; provider-specific vars override it.
# ---------------------------------------------------------------------------
_global_delay = os.getenv("API_CALL_DELAY", "")
ANTHROPIC_API_CALL_DELAY: int = int(os.getenv("ANTHROPIC_API_CALL_DELAY", _global_delay or "2"))
GEMINI_API_CALL_DELAY: int = int(os.getenv("GEMINI_API_CALL_DELAY", _global_delay or "10"))

# ---------------------------------------------------------------------------
# Provider-specific PDF extraction defaults
# ---------------------------------------------------------------------------
# chunk_pages: pages per API call when processing PDFs.
# None = send the entire document in one call (Anthropic handles large contexts well).
# Integer = split into chunks of that many pages (Gemini has tighter output limits).
PROVIDER_DEFAULTS: dict[str, dict] = {
    "anthropic": {"chunk_pages": None},
    "gemini": {"chunk_pages": 2},
}


def get_pdf_chunk_pages() -> int | None:
    """Return pages-per-chunk for the active provider (None = single call)."""
    return PROVIDER_DEFAULTS.get(LLM_PROVIDER, {}).get("chunk_pages", None)

# ---------------------------------------------------------------------------
# Process subdirectory names
# ---------------------------------------------------------------------------
PROCESS_SUBDIRS: list[str] = [
    "input",
    "extractions",
    "evidence_records",
    "verification",
    "narratives",
]
