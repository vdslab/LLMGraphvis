"""Provider/model options exposed to the frontend for per-chat selection.

Model ids here must stay in sync with the defaults in the provider adapters and
with pricing.py's MODEL_PRICING keys (unknown models just default to $0.0
estimated cost rather than erroring, so drift here degrades gracefully but
should still be avoided). LM Studio is added dynamically because its model id is
chosen by the user in LM Studio rather than by this application.
"""
import os
from typing import Any, Dict, List

from .providers.defaults import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
)
from .providers.lmstudio_provider import list_lmstudio_model_ids

PROVIDER_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "google",
        "label": "Google Gemini",
        "models": [
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
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
            {"id": "gpt-5.6-sol", "label": "GPT-5.6 Sol"},
            {"id": "gpt-5.6-terra", "label": "GPT-5.6 Terra"},
            {"id": "gpt-5.6-luna", "label": "GPT-5.6 Luna"},
        ],
    },
]

DEFAULT_PROVIDER = "google"

PROVIDER_MODEL_DEFAULTS = {
    "google": ("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    "anthropic": ("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL),
    "openai": ("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
}


def resolve_default_provider() -> str:
    """Return the process-wide provider used by chats without a provider pin."""
    configured = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    return configured or DEFAULT_PROVIDER


def resolve_default_model(
    provider_id: str, lmstudio_models: List[str]
) -> str:
    """Resolve the model an unpinned chat will actually use for a provider."""
    if provider_id == "lmstudio":
        configured = (os.getenv("LM_STUDIO_MODEL") or "").strip()
        return configured or (lmstudio_models[0] if lmstudio_models else "")

    provider_default = PROVIDER_MODEL_DEFAULTS.get(provider_id)
    if provider_default is None:
        return ""
    env_name, fallback = provider_default
    return (os.getenv(env_name) or "").strip() or fallback


def is_provider_available(provider_id: str) -> bool:
    """Return whether the provider has the credentials required to be used."""
    if provider_id == "openai":
        return bool((os.getenv("OPENAI_API_KEY") or "").strip())
    if provider_id == "lmstudio":
        return bool(list_lmstudio_model_ids())
    return True


def get_available_provider_catalog() -> List[Dict[str, Any]]:
    """Return only providers that are usable in the current environment."""
    lmstudio_models = list_lmstudio_model_ids()
    providers = [
        provider
        for provider in PROVIDER_CATALOG
        if is_provider_available(provider["id"])
    ]
    if lmstudio_models:
        providers.append(
            {
                "id": "lmstudio",
                "label": "LM Studio (Local)",
                "models": [
                    {"id": model_id, "label": model_id}
                    for model_id in lmstudio_models
                ],
            }
        )

    default_provider = resolve_default_provider()
    default_model = resolve_default_model(default_provider, lmstudio_models)
    return [
        {
            **provider,
            "models": [
                {
                    **model,
                    "default": (
                        provider["id"] == default_provider
                        and model["id"] == default_model
                    ),
                }
                for model in provider["models"]
            ],
        }
        for provider in providers
    ]
