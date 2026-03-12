"""Google Gemini provider implementation (google-genai SDK)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from google import genai
from google.genai import types

from gocam.config import (
    GEMINI_API_CALL_DELAY,
    GEMINI_API_KEY,
    GEMINI_FALLBACK_MODELS,
    GEMINI_MODEL,
)
from gocam.services.llm import LLMClient, _is_retryable

_MAX_TOKENS = 65536

# How long to wait before retrying the same model on quota exhaustion (seconds).
_QUOTA_COOLDOWN = 300  # 5 minutes


def _is_quota_exhausted(exc: Exception) -> bool:
    """Return True when the error is specifically a quota/rate-limit exhaustion."""
    msg = str(exc).lower()
    return any(x in msg for x in (
        "resource_exhausted", "resource exhausted",
        "quota exceeded", "429",
    ))


def _is_overloaded(exc: Exception) -> bool:
    """Return True for server-overloaded / rate-limit / unavailable errors."""
    msg = str(exc).lower()
    return any(x in msg for x in (
        "503", "overloaded", "service unavailable",
        "too many requests", "rate limit", "rate_limit",
        "resource_exhausted", "resource exhausted",
        "quota exceeded", "429",
    ))


class GeminiProvider(LLMClient):
    """Calls the Google Gemini API using the configured Gemini model."""

    def __init__(self) -> None:
        super().__init__()
        if not GEMINI_API_KEY:
            raise SystemExit(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file (see .env.example)."
            )
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._api_call_delay = GEMINI_API_CALL_DELAY
        self._model = GEMINI_MODEL
        # Build ordered fallback list (primary model first, then fallbacks,
        # skipping duplicates while preserving order).
        seen: set[str] = set()
        self._model_chain: list[str] = []
        for m in [GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]:
            if m not in seen:
                seen.add(m)
                self._model_chain.append(m)

    def _config(self, prompt_name: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self._build_system(prompt_name),
            max_output_tokens=_MAX_TOKENS,
        )

    # ------------------------------------------------------------------
    # Model-fallback wrapper
    # ------------------------------------------------------------------

    def _call_with_model_fallback(self, fn: Callable[[str], Any]) -> Any:
        """Try fn(model) with the primary model, then fallbacks on overload/quota errors.

        For each model in the chain:
        1. Try the call (with the standard retry logic from LLMClient).
        2. If it fails with an overload/quota error on the *first* model, wait
           _QUOTA_COOLDOWN seconds and retry once more.
        3. If still failing, move to the next model in the chain.
        4. If all models are exhausted, raise the last exception.

        Non-overload errors (e.g. invalid request, auth failure) are raised
        immediately without trying fallback models.
        """
        from gocam.utils.display import console

        last_exc: Exception | None = None

        for idx, model in enumerate(self._model_chain):
            self._model = model
            attempts = 2 if idx == 0 else 1  # primary model gets a cooldown retry

            for attempt in range(attempts):
                try:
                    return self._call_with_retry(lambda: fn(self._model))
                except Exception as exc:
                    last_exc = exc
                    if not _is_overloaded(exc):
                        raise  # non-overload error — don't fallback, just raise

                    if idx == 0 and attempt == 0:
                        # First failure on primary model: wait and retry
                        console.print(
                            f"[yellow]Model {model} overloaded/quota exhausted. "
                            f"Waiting {_QUOTA_COOLDOWN // 60} minutes before retrying…[/yellow]"
                        )
                        with console.status("") as status:
                            for remaining in range(_QUOTA_COOLDOWN, 0, -1):
                                mins, secs = divmod(remaining, 60)
                                status.update(
                                    f"[yellow]Cooldown: {mins}m {secs:02d}s remaining…[/yellow]"
                                )
                                time.sleep(1)
                    else:
                        # Either the cooldown retry failed or a fallback model failed
                        if idx + 1 < len(self._model_chain):
                            next_model = self._model_chain[idx + 1]
                            console.print(
                                f"[yellow]{model} overloaded/quota exhausted. "
                                f"Switching to fallback model: {next_model}[/yellow]"
                            )
                        else:
                            console.print(
                                f"[red]{model} overloaded/quota exhausted "
                                f"(last fallback). Aborting.[/red]"
                            )
                        break  # move to next model in chain

        # All models exhausted
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call_text(self, prompt_name: str, user_content: str) -> dict:
        response = self._call_with_model_fallback(
            lambda model: self._client.models.generate_content(
                model=model,
                config=self._config(prompt_name),
                contents=user_content,
            )
        )
        return self._parse_json(response.text)

    def call_vision(
        self,
        prompt_name: str,
        user_text: str,
        images: list[bytes],
    ) -> dict:
        parts: list = [
            types.Part.from_bytes(data=self._resize_image(img), mime_type="image/png")
            for img in images
        ]
        parts.append(user_text)
        response = self._call_with_model_fallback(
            lambda model: self._client.models.generate_content(
                model=model,
                config=self._config(prompt_name),
                contents=parts,
            )
        )
        return self._parse_json(response.text)

    def call_text_markdown(self, prompt_name: str, user_content: str) -> str:
        response = self._call_with_model_fallback(
            lambda model: self._client.models.generate_content(
                model=model,
                config=self._config(prompt_name),
                contents=user_content,
            )
        )
        return response.text
