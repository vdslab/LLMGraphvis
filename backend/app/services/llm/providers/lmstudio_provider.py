import os
from typing import Optional

from .openai_provider import OpenAIProvider

DEFAULT_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"


class LMStudioProvider(OpenAIProvider):
    """LM Studio adapter using its OpenAI-compatible Chat Completions API."""

    def __init__(self, model_name: Optional[str] = None):
        from openai import AsyncOpenAI

        configured_model = model_name or os.getenv("LM_STUDIO_MODEL")
        if not configured_model or not configured_model.strip():
            raise ValueError(
                "LM Studio requires a model id. Set LM_STUDIO_MODEL to the "
                "identifier shown in LM Studio, or select a configured model."
            )

        self.client = AsyncOpenAI(
            base_url=(
                os.getenv("LM_STUDIO_BASE_URL") or DEFAULT_LM_STUDIO_BASE_URL
            ).rstrip("/"),
            # The OpenAI SDK requires a value even when LM Studio authentication
            # is disabled. When authentication is enabled, use the real token.
            api_key=os.getenv("LM_STUDIO_API_KEY") or "lm-studio",
        )
        self.model_name = configured_model.strip()
