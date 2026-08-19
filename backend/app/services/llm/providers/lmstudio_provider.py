import os
from typing import List, Optional

import httpx

from app.core.logging import get_logger

from .openai_provider import OpenAIProvider

DEFAULT_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LM_STUDIO_DISCOVERY_TIMEOUT = 2.0

logger = get_logger(__name__)


def get_lmstudio_base_url() -> str:
    """Return the configured OpenAI-compatible API root without a trailing slash."""
    return (
        os.getenv("LM_STUDIO_BASE_URL") or DEFAULT_LM_STUDIO_BASE_URL
    ).rstrip("/")


def get_lmstudio_server_url() -> str:
    """Return the LM Studio server root used by its native management API."""
    base_url = get_lmstudio_base_url()
    return base_url[:-3] if base_url.endswith("/v1") else base_url


def list_lmstudio_model_ids() -> List[str]:
    """Return chat-capable model ids advertised by LM Studio's native API.

    An unavailable local server is an expected state, so discovery failures
    produce an empty list instead of breaking the provider catalog endpoint.
    """
    api_key = (os.getenv("LM_STUDIO_API_KEY") or "").strip()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None

    try:
        response = httpx.get(
            f"{get_lmstudio_server_url()}/api/v1/models",
            headers=headers,
            timeout=LM_STUDIO_DISCOVERY_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("models", []) if isinstance(payload, dict) else []
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        logger.debug("LM Studio model discovery unavailable: %s", exc)
        return []

    model_ids = []
    seen = set()
    for model in data if isinstance(data, list) else []:
        if not isinstance(model, dict) or model.get("type") != "llm":
            continue
        model_id = model.get("key")
        if not isinstance(model_id, str):
            continue
        model_id = model_id.strip()
        if model_id and model_id not in seen:
            model_ids.append(model_id)
            seen.add(model_id)
    return model_ids


class LMStudioProvider(OpenAIProvider):
    """LM Studio adapter using its OpenAI-compatible Chat Completions API."""

    def __init__(self, model_name: Optional[str] = None):
        from openai import AsyncOpenAI

        configured_model = model_name or os.getenv("LM_STUDIO_MODEL")
        if not configured_model or not configured_model.strip():
            discovered_models = list_lmstudio_model_ids()
            configured_model = discovered_models[0] if discovered_models else None
        if not configured_model or not configured_model.strip():
            raise ValueError(
                "LM Studio has no available model. Start its server and load a "
                "model, select a discovered model, or set LM_STUDIO_MODEL."
            )

        self.client = AsyncOpenAI(
            base_url=get_lmstudio_base_url(),
            # The OpenAI SDK requires a value even when LM Studio authentication
            # is disabled. When authentication is enabled, use the real token.
            api_key=os.getenv("LM_STUDIO_API_KEY") or "lm-studio",
        )
        self.model_name = configured_model.strip()
