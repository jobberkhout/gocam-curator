"""Google Gemini provider implementation (google-genai SDK)."""

from __future__ import annotations

from google import genai
from google.genai import types

from gocam.config import GEMINI_API_CALL_DELAY, GEMINI_API_KEY, GEMINI_MODEL
from gocam.services.llm import LLMClient

_MAX_TOKENS = 32768


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

    def _config(self, prompt_name: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self._build_system(prompt_name),
            max_output_tokens=_MAX_TOKENS,
        )

    def call_text(self, prompt_name: str, user_content: str) -> dict:
        response = self._call_with_retry(lambda: self._client.models.generate_content(
            model=GEMINI_MODEL,
            config=self._config(prompt_name),
            contents=user_content,
        ))
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
        response = self._call_with_retry(lambda: self._client.models.generate_content(
            model=GEMINI_MODEL,
            config=self._config(prompt_name),
            contents=parts,
        ))
        return self._parse_json(response.text)

    def call_text_markdown(self, prompt_name: str, user_content: str) -> str:
        response = self._call_with_retry(lambda: self._client.models.generate_content(
            model=GEMINI_MODEL,
            config=self._config(prompt_name),
            contents=user_content,
        ))
        return response.text
