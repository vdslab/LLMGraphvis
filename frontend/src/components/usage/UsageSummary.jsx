import { formatTokenCount, formatTotalCost } from '../../utils/usageFormat';

// The token counts and cost of a usage total, in the normalized meaning of
// ADR 0025: input includes cache reads/writes, output includes reasoning.
const UsageSummary = ({ totals, showRequests = true }) => {
  const uncached = Math.max(
    (totals.input_tokens || 0) - (totals.cached_input_tokens || 0) - (totals.cache_write_tokens || 0),
    0,
  );
  const cells = [
    {
      label: 'Input',
      value: totals.input_tokens,
      detail: [
        `${formatTokenCount(uncached)} new`,
        totals.cached_input_tokens ? `${formatTokenCount(totals.cached_input_tokens)} cache read` : null,
        totals.cache_write_tokens ? `${formatTokenCount(totals.cache_write_tokens)} cache write` : null,
      ].filter(Boolean).join(' · '),
    },
    {
      label: 'Output',
      value: totals.output_tokens,
      detail: totals.reasoning_tokens
        ? `${formatTokenCount(totals.reasoning_tokens)} reasoning`
        : null,
    },
  ];

  return (
    <div className="usage-summary">
      {cells.map((cell) => (
        <div key={cell.label} className="usage-summary__cell">
          <span className="usage-summary__label">{cell.label}</span>
          <span className="usage-summary__value" title={(cell.value || 0).toLocaleString()}>
            {formatTokenCount(cell.value)}
          </span>
          {cell.detail && <span className="usage-summary__detail">{cell.detail}</span>}
        </div>
      ))}
      <div className="usage-summary__cell">
        <span className="usage-summary__label">Est. cost</span>
        <span className="usage-summary__value">{formatTotalCost(totals)}</span>
        <span className="usage-summary__detail">
          {[
            showRequests && totals.request_count ? `${totals.request_count} requests` : null,
            totals.unpriced_count ? `${totals.unpriced_count} unpriced` : null,
          ].filter(Boolean).join(' · ') || null}
        </span>
      </div>
    </div>
  );
};

export default UsageSummary;
