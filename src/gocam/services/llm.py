"""Provider-agnostic LLM interface.

All code outside this package imports only from here:

    from gocam.services.llm import get_llm_client

The concrete provider (Anthropic / Gemini) is selected at runtime via the
LLM_PROVIDER environment variable.
"""

from __future__ import annotations

import base64
import io
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from PIL import Image

from gocam.utils.io import load_prompt, load_system_prompt

_MAX_IMAGE_DIMENSION = 1568  # longest side in pixels; both APIs recommend this

# Retry delays in seconds for each successive attempt.
# Override with LLM_RETRY_DELAYS env var (comma-separated, e.g. "30,60,120").
def _load_retry_delays() -> list[int]:
    import os
    env = os.getenv("LLM_RETRY_DELAYS", "").strip()
    if env:
        try:
            return [int(s.strip()) for s in env.split(",") if s.strip()]
        except ValueError:
            pass
    return [30, 60, 120, 120]

_RETRY_DELAYS = _load_retry_delays()


def _is_retryable(exc: Exception) -> bool:
    """Return True for rate-limit (429) and server-overloaded (503) errors."""
    msg = str(exc).lower()
    return any(x in msg for x in (
        "503", "429", "rate limit", "rate_limit",
        "overloaded", "too many requests", "service unavailable",
        "resource exhausted",
    ))


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to salvage a truncated JSON object by closing open structures.

    Works backwards from the truncation point: strips the last partial
    value/key, then appends the necessary closing brackets and braces.
    Returns the parsed dict on success, or None if repair fails.
    """
    text = text.strip()
    if not text.startswith("{"):
        return None

    # Strip trailing partial tokens: cut back to the last complete
    # value delimiter (, ] } or a quoted string ending with ")
    # Try increasingly aggressive truncation points.
    for cut_chars in ("]", "}", ",", '"'):
        idx = text.rfind(cut_chars)
        if idx == -1:
            continue
        fragment = text[: idx + 1]

        # Count open/close brackets and braces
        open_braces = fragment.count("{") - fragment.count("}")
        open_brackets = fragment.count("[") - fragment.count("]")

        if open_braces < 0 or open_brackets < 0:
            continue

        # Close everything that's still open
        suffix = "]" * open_brackets + "}" * open_braces
        try:
            result = json.loads(fragment + suffix)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue

    return None


class LLMClient(ABC):
    """Abstract base for all LLM provider implementations.

    Shared helpers live here so providers only implement the API calls.
    """

    def __init__(self) -> None:
        self._last_call_time: float = 0.0
        self._api_call_delay: int = 0  # seconds; set by each subclass

    # ------------------------------------------------------------------
    # Rate-limiting and retry (shared by all providers)
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Sleep the remaining gap if calls are arriving faster than the delay."""
        if not self._api_call_delay:
            return
        elapsed = time.monotonic() - self._last_call_time
        if self._last_call_time and elapsed < self._api_call_delay:
            time.sleep(self._api_call_delay - elapsed)
        self._last_call_time = time.monotonic()

    def _call_with_retry(self, fn: Callable[[], Any]) -> Any:
        """Apply rate-limiting then call fn(), retrying on 429/503 with backoff."""
        from gocam.utils.display import console  # local import avoids circular dep
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                self._rate_limit()
                return fn()
            except Exception as exc:
                if not _is_retryable(exc) or attempt == len(_RETRY_DELAYS):
                    raise
                delay = _RETRY_DELAYS[attempt]
                with console.status("") as status:
                    for remaining in range(delay, 0, -1):
                        status.update(
                            f"[yellow]Model overloaded. Retrying in {remaining}s... "
                            f"(attempt {attempt + 1}/{len(_RETRY_DELAYS)})[/yellow]"
                        )
                        time.sleep(1)

    # ------------------------------------------------------------------
    # Shared helpers (available to all providers)
    # ------------------------------------------------------------------

    def _build_system(self, prompt_name: str) -> str:
        """Concatenate system.md and the command-specific prompt."""
        return load_system_prompt() + "\n\n---\n\n" + load_prompt(prompt_name)

    def _resize_image(self, image_bytes: bytes) -> bytes:
        """Downscale image if its longest side exceeds the API limit."""
        img = Image.open(io.BytesIO(image_bytes))
        if max(img.size) > _MAX_IMAGE_DIMENSION:
            img.thumbnail((_MAX_IMAGE_DIMENSION, _MAX_IMAGE_DIMENSION), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _to_base64_png(self, image_bytes: bytes) -> str:
        """Resize and return as a base64-encoded PNG string."""
        return base64.standard_b64encode(self._resize_image(image_bytes)).decode()

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract JSON from a model response, stripping markdown code fences.

        Handles nested objects correctly by splitting on fence markers rather
        than using a greedy/non-greedy regex over the JSON body.  If the JSON
        is truncated (output hit the token limit), attempts to repair it by
        closing open brackets/braces so partial data is not lost.
        """
        text = text.strip()
        # Fast path: the whole response is valid JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Extract content between ``` fences; odd-indexed parts are inside fences
        candidates: list[str] = []
        if "```" in text:
            for part in text.split("```")[1::2]:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    candidates.append(candidate)

        # Truncation repair: try to close open brackets/braces on the best
        # candidate (fenced JSON first, otherwise the raw text).
        for raw in (candidates or [text]):
            repaired = _repair_truncated_json(raw)
            if repaired is not None:
                return repaired

        raise ValueError(
            f"Could not parse JSON from model response.\nFirst 500 chars:\n{text[:500]}"
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def call_text(self, prompt_name: str, user_content: str) -> dict:
        """Send a text-only request; return parsed JSON dict."""

    @abstractmethod
    def call_vision(
        self,
        prompt_name: str,
        user_text: str,
        images: list[bytes],
    ) -> dict:
        """Send a request with one or more images; return parsed JSON dict."""

    @abstractmethod
    def call_text_markdown(self, prompt_name: str, user_content: str) -> str:
        """Send a text-only request; return the raw string (for Markdown output)."""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_llm_client() -> LLMClient:
    """Instantiate and return the provider configured via LLM_PROVIDER in .env."""
    from gocam.config import LLM_PROVIDER  # imported here to avoid circular imports at module load

    provider = LLM_PROVIDER.lower()

    if provider == "anthropic":
        from gocam.services.providers.anthropic import AnthropicProvider
        return AnthropicProvider()

    if provider == "gemini":
        from gocam.services.providers.gemini import GeminiProvider
        return GeminiProvider()

    if provider == "vertex":
        from gocam.services.providers.vertex import VertexProvider
        return VertexProvider()

    raise SystemExit(
        f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. "
        "Set LLM_PROVIDER=anthropic, gemini, or vertex in your .env file."
    )
