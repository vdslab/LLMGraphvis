"""
Estimated USD cost per LLM call, based on token usage.

IMPORTANT CAVEATS (verify before relying on these for real billing decisions):
- This system can call Claude/Gemini either directly or via Vertex AI (VERTEX_PROJECT_ID
  env var). Claude's per-token pricing via Vertex AI matches Anthropic's direct API pricing
  (billing just routes through GCP invoicing) as of this writing — but re-verify against
  https://platform.claude.com/docs/en/pricing before relying on this for real costs.
  Gemini's Vertex AI pricing should be independently verified against the Vertex AI Model
  Garden pricing page, NOT assumed identical to Google AI Studio pricing.
- Whether `cached_input_tokens` is already included inside `input_tokens` (double-counting
  risk) differs by provider and must be verified empirically (log both values from a real
  cached request and compare against the expected full prompt size) before trusting the
  cost math below at the margins. This implementation currently assumes cached tokens are
  NOT double-counted inside input_tokens for Anthropic (per Anthropic's documented API
  semantics: cache_read_input_tokens is reported separately from input_tokens) - verify this
  matches what you observe in production before relying on it.
"""

# USD per 1,000,000 tokens.
MODEL_PRICING = {
    # Anthropic — current defaults used by this codebase (see anthropic_provider.py
    # CLAUDE_MODEL default) plus adjacent tiers, per platform.claude.com/docs/en/pricing.
    "claude-opus-4-8": {"input": 5.00, "output": 25.00, "cached_input": 0.50},
    "claude-opus-4-7": {"input": 5.00, "output": 25.00, "cached_input": 0.50},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00, "cached_input": 0.50},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00, "cached_input": 0.30},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cached_input": 0.30},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cached_input": 0.10},
    # Google Gemini — current default used by this codebase (see google_genai.py
    # GEMINI_MODEL default) plus adjacent tier.
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cached_input": 0.075},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "cached_input": 0.31},
}
DEFAULT_PRICING = {"input": 0.0, "output": 0.0, "cached_input": 0.0}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
    """
    Returns an estimated USD cost. Unknown models return $0.0 rather than raising,
    so a newly-introduced model name never crashes usage tracking - it just under-reports
    cost until MODEL_PRICING is updated.
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    billable_input = max(input_tokens - cached_input_tokens, 0)
    cost = (
        billable_input * pricing["input"]
        + cached_input_tokens * pricing.get("cached_input", pricing["input"])
        + output_tokens * pricing["output"]
    ) / 1_000_000
    return cost
