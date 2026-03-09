"""Anthropic Claude provider implementation."""

from __future__ import annotations

import anthropic

from gocam.config import ANTHROPIC_API_CALL_DELAY, ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from gocam.services.llm import LLMClient

_MAX_TOKENS = 8192


class AnthropicProvider(LLMClient):
    """Calls the Anthropic Messages API using the configured Claude model."""

    def __init__(self) -> None:
        super().__init__()
        if not ANTHROPIC_API_KEY:
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file (see .env.example)."
            )
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._api_call_delay = ANTHROPIC_API_CALL_DELAY

    def call_text(self, prompt_name: str, user_content: str) -> dict:
        response = self._call_with_retry(lambda: self._client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=_MAX_TOKENS,
            system=self._build_system(prompt_name),
            messages=[{"role": "user", "content": user_content}],
        ))
        return self._parse_json(response.content[0].text)

    def call_vision(
        self,
        prompt_name: str,
        user_text: str,
        images: list[bytes],
    ) -> dict:
        content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": self._to_base64_png(img),
                },
            }
            for img in images
        ]
        content.append({"type": "text", "text": user_text})
        response = self._call_with_retry(lambda: self._client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=_MAX_TOKENS,
            system=self._build_system(prompt_name),
            messages=[{"role": "user", "content": content}],
        ))
        return self._parse_json(response.content[0].text)

    def call_text_markdown(self, prompt_name: str, user_content: str) -> str:
        response = self._call_with_retry(lambda: self._client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=_MAX_TOKENS,
            system=self._build_system(prompt_name),
            messages=[{"role": "user", "content": user_content}],
        ))
        return response.content[0].text
