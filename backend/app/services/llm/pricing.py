"""
Estimated USD cost of LLM calls, from normalized token usage.

Every provider adapter reports `UsageData` with one meaning (see its docstring
and ADR 0025): `input_tokens` includes cache reads and writes, `output_tokens`
includes reasoning. So one formula serves every provider:

    uncached input  x input rate
  + cache reads     x cached_input rate
  + cache writes    x cache_write rate (Anthropic bills a premium; others 0 tokens)
  + output          x output rate

Rates are list prices per 1M tokens and must be re-checked against each
provider's pricing page when a model is added. Gemini Pro entries use the
<=200k-token tier. Vertex AI routing is assumed to bill at the same rates.
"""

from typing import Dict, Optional

from .providers.types import UsageData

# USD per 1,000,000 tokens.
MODEL_PRICING = {
    # Anthropic — current defaults used by this codebase (see anthropic_provider.py
    # CLAUDE_MODEL default) plus adjacent tiers, per platform.claude.com/docs/en/pricing.
    # cache_write is the 5-minute cache TTL rate: 1.25x input.
    "claude-opus-4-8": {"input": 5.00, "output": 25.00, "cached_input": 0.50, "cache_write": 6.25},
    "claude-opus-4-7": {"input": 5.00, "output": 25.00, "cached_input": 0.50, "cache_write": 6.25},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00, "cached_input": 0.50, "cache_write": 6.25},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00, "cached_input": 0.30, "cache_write": 3.75},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cached_input": 0.30, "cache_write": 3.75},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cached_input": 0.10, "cache_write": 1.25},
    # Google Gemini — standard Google AI Studio text rates. Pro entries use the
    # <=200k-token tier because this estimator does not receive prompt size.
    "gemini-3.8-flash": {"input": 0.75, "output": 3.75, "cached_input": 0.075},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00, "cached_input": 0.20},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50, "cached_input": 0.03},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cached_input": 0.075},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "cached_input": 0.31},
    # OpenAI — prices published for the GPT-5.6 family.
    "gpt-5.6-sol": {"input": 5.00, "output": 30.00, "cached_input": 0.50},
    "gpt-5.6-terra": {"input": 2.50, "output": 15.00, "cached_input": 0.25},
    "gpt-5.6-luna": {"input": 1.00, "output": 6.00, "cached_input": 0.10},
}

# LM Studio runs locally; its models cost nothing per token.
FREE_PROVIDERS = {"lmstudio"}


def get_model_pricing(model: str, provider: str = "") -> Optional[Dict[str, float]]:
    """Per-1M-token rates for a model, or None when the rate is unknown."""
    if provider in FREE_PROVIDERS:
        return {"input": 0.0, "output": 0.0, "cached_input": 0.0, "cache_write": 0.0}
    return MODEL_PRICING.get(model)


def estimate_cost_usd(
    model: str,
    usage: UsageData,
    provider: str = "",
) -> Optional[float]:
    """Estimated USD cost of `usage`, or None when the model has no known rate.

    None, not 0.0, so an unpriced model reads as "unknown" rather than "free".
    """
    pricing = get_model_pricing(model, provider)
    if pricing is None:
        return None
    input_rate = pricing["input"]
    cached = usage.cached_input_tokens
    written = usage.cache_write_tokens
    uncached = max(usage.input_tokens - cached - written, 0)
    return (
        uncached * input_rate
        + cached * pricing.get("cached_input", input_rate)
        + written * pricing.get("cache_write", input_rate)
        + usage.output_tokens * pricing["output"]
    ) / 1_000_000
