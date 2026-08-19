"""Provider/model options exposed to the frontend for per-chat selection.

Model ids here must stay in sync with the defaults in the provider adapters and
with pricing.py's MODEL_PRICING keys (unknown models just default to $0.0
estimated cost rather than erroring, so drift here degrades gracefully but
should still be avoided). LM Studio is added dynamically because its model id is
chosen by the user in LM Studio rather than by this application.
"""
import os
from typing import Any, Dict, List

PROVIDER_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "google",
        "label": "Google Gemini",
        "models": [
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "default": True},
            {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
        ],
    },
    {
        "id": "anthropic",
        "label": "Anthropic Claude",
        "models": [
            {"id": "claude-opus-4-8", "label": "Claude Opus 4.8"},
            {"id": "claude-sonnet-5", "label": "Claude Sonnet 5"},
            {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5"},
        ],
    },
    {
        "id": "openai",
        "label": "OpenAI ChatGPT",
        "models": [
            {"id": "gpt-5.6-sol", "label": "GPT-5.6 Sol", "default": True},
            {"id": "gpt-5.6-terra", "label": "GPT-5.6 Terra"},
            {"id": "gpt-5.6-luna", "label": "GPT-5.6 Luna"},
        ],
    },
]

DEFAULT_PROVIDER = "google"


def is_provider_available(provider_id: str) -> bool:
    """Return whether the provider has the credentials required to be used."""
    if provider_id == "openai":
        return bool((os.getenv("OPENAI_API_KEY") or "").strip())
    if provider_id == "lmstudio":
        return bool((os.getenv("LM_STUDIO_MODEL") or "").strip())
    return True


def get_available_provider_catalog() -> List[Dict[str, Any]]:
    """Return only providers that are usable in the current environment."""
    providers = [
        provider
        for provider in PROVIDER_CATALOG
        if is_provider_available(provider["id"])
    ]
    lmstudio_model = (os.getenv("LM_STUDIO_MODEL") or "").strip()
    if lmstudio_model:
        providers.append(
            {
                "id": "lmstudio",
                "label": "LM Studio (Local)",
                "models": [{"id": lmstudio_model, "label": lmstudio_model}],
            }
        )
    return providers
