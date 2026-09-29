// Formatting for token usage and estimated cost (ADR 0025).

// Compact token count, e.g. 1234 -> "1.2K", 1234567 -> "1.2M".
export const formatTokenCount = (n) => {
  const value = n || 0;
  if (value < 1000) return `${value}`;
  if (value < 1000000) return `${(value / 1000).toFixed(1)}K`;
  return `${(value / 1000000).toFixed(1)}M`;
};

// Costs under a cent still need to be visible (e.g. $0.0032). null means the
// model has no known rate, which must not read as free.
export const formatCost = (cost) => {
  if (cost === null || cost === undefined) return '—';
  if (cost > 0 && cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
};

// A total whose cost leaves out unpriced entries says so.
export const formatTotalCost = (totals) => {
  const cost = formatCost(totals?.estimated_cost_usd ?? 0);
  return totals?.unpriced_count ? `${cost}+` : cost;
};

export const PURPOSE_LABELS = {
  agent_turn: 'Turn',
  title: 'Chat title',
};

// The same counts, summed. Works for the stored totals and the live turn.
export const addUsage = (a, b) => ({
  input_tokens: (a?.input_tokens || 0) + (b?.input_tokens || 0),
  output_tokens: (a?.output_tokens || 0) + (b?.output_tokens || 0),
  cached_input_tokens: (a?.cached_input_tokens || 0) + (b?.cached_input_tokens || 0),
  cache_write_tokens: (a?.cache_write_tokens || 0) + (b?.cache_write_tokens || 0),
  reasoning_tokens: (a?.reasoning_tokens || 0) + (b?.reasoning_tokens || 0),
  estimated_cost_usd: (a?.estimated_cost_usd || 0) + (b?.estimated_cost_usd || 0),
  unpriced_count:
    (a?.unpriced_count || 0) +
    (b?.unpriced_count || 0) +
    (b && b.estimated_cost_usd === null && b.input_tokens ? 1 : 0),
});
