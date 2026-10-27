"""Estimated USD cost of LLM calls, from normalized token usage.

Every provider adapter reports `UsageData` with one meaning (see its docstring
and ADR 0025): `input_tokens` includes cache reads and writes, `output_tokens`
includes reasoning. So one formula serves every provider:

    uncached input  x input rate
  + cache reads     x cached_input rate
  + cache writes    x cache_write rate (Anthropic bills a premium; others 0 tokens)
  + output          x output rate

A model's rate depends on two more things (ADR 0043):

- **When.** Each model lists its prices in date order; the one in force on the
  day of the call applies. Announced price changes are entered ahead of time.
- **How long the prompt is.** Some models charge more above a prompt size. That
  is decided per request, so a turn is priced call by call from `TurnUsage.calls`.

Rates are list prices per 1M tokens from each provider's pricing page
(Anthropic first-party API, Google AI Studio paid tier, OpenAI standard tier),
checked on 2026-10-27. Re-check them when a model is added. Vertex AI routing is
assumed to bill at the same rates. Gemini context-cache storage, billed per hour,
is not included.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, Optional, Tuple

from .providers.types import TurnUsage, UsageData


@dataclass(frozen=True)
class Rates:
    """USD per 1,000,000 tokens. A missing cache rate bills at the input rate."""

    input: float
    output: float
    cached_input: Optional[float] = None
    cache_write: Optional[float] = None


@dataclass(frozen=True)
class Price:
    """The rates of one model from `since` (None: from the start) onwards."""

    rates: Rates
    long_context: Optional[Rates] = None
    long_context_above: int = 0  # prompt tokens per request
    since: Optional[date] = None

    def rates_for(self, prompt_tokens: int) -> Rates:
        if self.long_context is not None and prompt_tokens > self.long_context_above:
            return self.long_context
        return self.rates


def _claude(input: float, output: float, cached: float, write: float) -> Price:
    # cache_write is the 5-minute cache TTL rate.
    return Price(Rates(input, output, cached_input=cached, cache_write=write))


_OPUS_5 = _claude(5.00, 25.00, 0.50, 6.25)
_GEMINI_FLASH = Price(Rates(0.75, 3.75, cached_input=0.075))
_GEMINI_FLASH_2027 = Price(Rates(1.50, 7.50, cached_input=0.15), since=date(2027, 1, 1))
# OpenAI publishes no long-context cached rate; it is assumed to double like
# the other two.
_OPENAI_LONG_ABOVE = 272_000


def _openai(input: float, output: float, cached: float, long_output: float) -> Price:
    return Price(
        Rates(input, output, cached_input=cached),
        long_context=Rates(input * 2, long_output, cached_input=cached * 2),
        long_context_above=_OPENAI_LONG_ABOVE,
    )


# Prices of each model in date order.
MODEL_PRICING: Dict[str, Tuple[Price, ...]] = {
    # Anthropic
    "claude-opus-5-5": (_claude(4.00, 20.00, 0.20, 5.00),),
    "claude-opus-5": (_OPUS_5,),
    "claude-opus-4-8": (_OPUS_5,),
    "claude-opus-4-7": (_OPUS_5,),
    "claude-opus-4-6": (_OPUS_5,),
    "claude-sonnet-5-5": (_claude(2.00, 10.00, 0.10, 2.50),),
    "claude-sonnet-5": (_claude(2.00, 10.00, 0.20, 2.50),),
    "claude-sonnet-4-6": (_claude(3.00, 15.00, 0.30, 3.75),),
    "claude-haiku-5-5": (
        Price(
            Rates(0.10, 0.50, cached_input=0.01, cache_write=0.125),
            long_context=Rates(0.50, 2.50, cached_input=0.05, cache_write=0.625),
            long_context_above=100_000,
        ),
    ),
    "claude-haiku-4-5": (_claude(1.00, 5.00, 0.10, 1.25),),
    # Google Gemini
    "gemini-4-argon": (
        Price(Rates(2.00, 10.00, cached_input=0.10)),
        Price(Rates(4.00, 20.00, cached_input=0.20), since=date(2026, 12, 1)),
    ),
    "gemini-3.8-flash": (_GEMINI_FLASH, _GEMINI_FLASH_2027),
    "gemini-3.6-flash": (_GEMINI_FLASH, _GEMINI_FLASH_2027),
    "gemini-3.5-flash-lite": (Price(Rates(0.30, 2.50, cached_input=0.03)),),
    "gemini-3.1-flash-lite": (Price(Rates(0.25, 1.50, cached_input=0.025)),),
    "gemini-3.1-pro-preview": (
        Price(
            Rates(2.00, 12.00, cached_input=0.20),
            long_context=Rates(4.00, 18.00, cached_input=0.40),
            long_context_above=200_000,
        ),
    ),
    "gemini-2.5-pro": (
        Price(
            Rates(1.25, 10.00, cached_input=0.125),
            long_context=Rates(2.50, 15.00, cached_input=0.25),
            long_context_above=200_000,
        ),
    ),
    "gemini-2.5-flash": (Price(Rates(0.30, 2.50, cached_input=0.03)),),
    # OpenAI. GPT-5.6 Sol's rate is promotional until at least 2026-11-21;
    # enter its next rate here once OpenAI announces it.
    "gpt-5.6-sol": (_openai(4.00, 20.00, 0.40, 30.00),),
    "gpt-5.6-terra": (_openai(2.00, 12.00, 0.20, 18.00),),
    "gpt-5.6-luna": (_openai(0.20, 1.20, 0.02, 1.80),),
    "gpt-6.1-sol": (_openai(2.00, 10.00, 0.10, 15.00),),
    "gpt-6.1-terra": (_openai(1.00, 5.00, 0.05, 7.50),),
    "gpt-6-luna": (_openai(0.10, 0.50, 0.01, 0.75),),
}

# LM Studio runs locally; its models cost nothing per token.
FREE_PROVIDERS = {"lmstudio"}
_FREE = Price(Rates(0.0, 0.0, cached_input=0.0, cache_write=0.0))


def get_model_pricing(
    model: str, provider: str = "", on: Optional[date] = None
) -> Optional[Price]:
    """The price of a model on `on` (default: today, UTC), or None when unknown."""
    if provider in FREE_PROVIDERS:
        return _FREE
    prices = MODEL_PRICING.get(model)
    if not prices:
        return None
    on = on or datetime.now(timezone.utc).date()
    current = None
    for price in prices:
        if price.since is None or price.since <= on:
            current = price
    return current


def _call_cost(rates: Rates, usage: UsageData) -> float:
    cached = usage.cached_input_tokens
    written = usage.cache_write_tokens
    uncached = max(usage.input_tokens - cached - written, 0)
    cached_rate = rates.input if rates.cached_input is None else rates.cached_input
    write_rate = rates.input if rates.cache_write is None else rates.cache_write
    return (
        uncached * rates.input
        + cached * cached_rate
        + written * write_rate
        + usage.output_tokens * rates.output
    ) / 1_000_000


def estimate_cost_usd(
    model: str,
    usage: UsageData,
    provider: str = "",
    on: Optional[date] = None,
) -> Optional[float]:
    """Estimated USD cost of `usage`, or None when the model has no known rate.

    None, not 0.0, so an unpriced model reads as "unknown" rather than "free".
    A `TurnUsage` is priced per generate() call, since the long-context rate
    depends on each request's prompt size.
    """
    price = get_model_pricing(model, provider, on)
    if price is None:
        return None
    calls = (
        [UsageData(**call) for call in usage.calls]
        if isinstance(usage, TurnUsage) and usage.calls
        else [usage]
    )
    return sum(_call_cost(price.rates_for(call.input_tokens), call) for call in calls)
