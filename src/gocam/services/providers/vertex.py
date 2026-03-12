"""Google Vertex AI provider — same Gemini models, higher quotas, project-based auth."""

from __future__ import annotations

from google import genai

from gocam.config import (
    GEMINI_FALLBACK_MODELS,
    GEMINI_MODEL,
    VERTEX_API_CALL_DELAY,
    VERTEX_LOCATION,
    VERTEX_PROJECT,
)
from gocam.services.providers.gemini import GeminiProvider


class VertexProvider(GeminiProvider):
    """Gemini via Vertex AI (uses Application Default Credentials, not an API key).

    Inherits all fallback, retry, and generate_content logic from GeminiProvider.
    Only the client initialisation differs.
    """

    def __init__(self) -> None:
        # Skip GeminiProvider.__init__ — we need a different client.
        # Call LLMClient.__init__ directly.
        super(GeminiProvider, self).__init__()

        if not VERTEX_PROJECT:
            raise SystemExit(
                "GOOGLE_CLOUD_PROJECT (or VERTEX_PROJECT) is not set. "
                "Set it in your .env file or environment.\n"
                "Also make sure Application Default Credentials are configured:\n"
                "  gcloud auth application-default login"
            )

        self._client = genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT,
            location=VERTEX_LOCATION,
        )
        self._api_call_delay = VERTEX_API_CALL_DELAY
        self._model = GEMINI_MODEL

        # Build model fallback chain (same logic as GeminiProvider)
        seen: set[str] = set()
        self._model_chain: list[str] = []
        for m in [GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]:
            if m not in seen:
                seen.add(m)
                self._model_chain.append(m)
