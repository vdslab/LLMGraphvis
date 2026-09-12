import { useChatStore } from '../stores/chatStore';

// Compact token count formatter, e.g. 1234 -> "1.2K", 1234567 -> "1.2M".
// Kept local/tiny on purpose (Stage 7 constraint: no new dependency for this).
const formatTokenCount = (n) => {
  if (n < 1000) return `${n}`;
  if (n < 1000000) return `${(n / 1000).toFixed(1)}K`;
  return `${(n / 1000000).toFixed(1)}M`;
};

// Cost formatting: costs under a cent still need to be visible (e.g. $0.0032),
// so use more decimal places for small values rather than rounding to $0.00.
const formatCost = (cost) => {
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
};

const UsageBadge = () => {
  const chatUsage = useChatStore((state) => state.chatUsage);
  const currentTurnUsage = useChatStore((state) => state.currentTurnUsage);

  const totalInputTokens = chatUsage.inputTokens + currentTurnUsage.inputTokens;
  const totalOutputTokens = chatUsage.outputTokens + currentTurnUsage.outputTokens;
  const totalTokens = totalInputTokens + totalOutputTokens;
  const totalCost = chatUsage.estimatedCostUsd + currentTurnUsage.estimatedCostUsd;

  if (totalTokens === 0) return null;

  const title = [
    `Input: ${totalInputTokens.toLocaleString()}`,
    `Output: ${totalOutputTokens.toLocaleString()}`,
    currentTurnUsage.provider ? `Provider: ${currentTurnUsage.provider}` : null,
    currentTurnUsage.model ? `Model: ${currentTurnUsage.model}` : null,
  ].filter(Boolean).join(' · ');

  return (
    <div
      title={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.4rem',
        padding: '0.3125rem 0.75rem',
        backgroundColor: 'var(--md-sys-color-surface-container-high)',
        borderRadius: 'var(--md-sys-shape-full)',
        border: '1px solid var(--md-sys-color-outline-subtle)',
        fontSize: '0.78125rem',
        fontWeight: 600,
        color: 'var(--md-sys-color-on-surface-variant)',
        maxWidth: '100%',
        minWidth: 0,
        flexShrink: 1,
      }}
    >
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {formatTokenCount(totalTokens)} tokens · {formatCost(totalCost)}
      </span>
    </div>
  );
};

export default UsageBadge;
