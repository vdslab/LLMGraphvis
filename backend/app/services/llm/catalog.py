"""Provider/model options exposed to the frontend for per-chat selection.

Model ids here must stay in sync with the defaults in providers/anthropic_provider.py
and providers/google_genai.py, and with pricing.py's MODEL_PRICING keys (unknown
models just default to $0.0 estimated cost rather than erroring, so drift here
degrades gracefully but should still be avoided).
"""
from typing import Any, Dict, List

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
]

DEFAULT_PROVIDER = "google"
