import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useChatStore } from '../stores/chatStore';
import UsageSummary from './usage/UsageSummary';
import {
  PURPOSE_LABELS,
  addUsage,
  formatCost,
  formatTokenCount,
  formatTotalCost,
} from '../utils/usageFormat';
import './usage/usage.css';

const POPOVER_WIDTH = 420;
const VIEWPORT_GUTTER = 16;

const formatTime = (iso) => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
};

const UsageEntry = ({ entry }) => {
  const [open, setOpen] = useState(false);
  const calls = entry.calls || [];
  const expandable = calls.length > 1;

  return (
    <li className="usage-entry">
      <button
        type="button"
        className="usage-entry__row"
        onClick={() => expandable && setOpen((v) => !v)}
        aria-expanded={expandable ? open : undefined}
        disabled={!expandable}
      >
        <ChevronRight
          size={14}
          aria-hidden
          className="usage-entry__chevron"
          style={{ visibility: expandable ? 'visible' : 'hidden', transform: open ? 'rotate(90deg)' : undefined }}
        />
        <span className="usage-entry__what">
          <span>{PURPOSE_LABELS[entry.purpose] || entry.purpose}</span>
          <span className="usage-entry__meta">
            {formatTime(entry.created_at)} · {entry.model}
            {calls.length > 1 ? ` · ${calls.length} requests` : ''}
          </span>
        </span>
        <span className="usage-entry__num" title="Input tokens">{formatTokenCount(entry.input_tokens)}</span>
        <span className="usage-entry__num" title="Output tokens">{formatTokenCount(entry.output_tokens)}</span>
        <span className="usage-entry__num">{formatCost(entry.estimated_cost_usd)}</span>
      </button>
      {open && (
        <table className="usage-calls">
          <thead>
            <tr><th>#</th><th>Input</th><th>Cached</th><th>Output</th><th>Reasoning</th></tr>
          </thead>
          <tbody>
            {calls.map((call, index) => (
              <tr key={index}>
                <td>{index + 1}</td>
                <td>{(call.input_tokens || 0).toLocaleString()}</td>
                <td>{(call.cached_input_tokens || 0).toLocaleString()}</td>
                <td>{(call.output_tokens || 0).toLocaleString()}</td>
                <td>{(call.reasoning_tokens || 0).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </li>
  );
};

const UsageBadge = () => {
  const chatId = useChatStore((state) => state.chatId);
  const chatUsage = useChatStore((state) => state.chatUsage);
  const currentTurnUsage = useChatStore((state) => state.currentTurnUsage);
  const fetchChatUsage = useChatStore((state) => state.fetchChatUsage);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState(null);
  const buttonRef = useRef(null);
  const popoverRef = useRef(null);

  // The chat panel is narrow and clips its overflow, so the popover lives in
  // a portal, fixed below the badge and kept inside the viewport.
  useLayoutEffect(() => {
    if (!open) return undefined;
    const place = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(POPOVER_WIDTH, window.innerWidth - 2 * VIEWPORT_GUTTER);
      const left = Math.min(
        Math.max(rect.right - width, VIEWPORT_GUTTER),
        window.innerWidth - width - VIEWPORT_GUTTER,
      );
      setPosition({ top: rect.bottom + 6, left, width });
    };
    place();
    window.addEventListener('resize', place);
    return () => window.removeEventListener('resize', place);
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event) => {
      const inside = [buttonRef.current, popoverRef.current]
        .some((node) => node && node.contains(event.target));
      if (!inside) setOpen(false);
    };
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // Stored usage of another chat must never show under this one.
  const stored = chatUsage.chatId === chatId ? chatUsage : null;
  const liveTurn = currentTurnUsage.input_tokens || currentTurnUsage.output_tokens
    ? currentTurnUsage
    : null;
  const totals = {
    ...(stored?.totals || {}),
    ...addUsage(stored?.totals, liveTurn),
  };
  const totalTokens = totals.input_tokens + totals.output_tokens;

  if (totalTokens === 0) return null;

  const toggle = () => {
    if (!open) fetchChatUsage().catch(() => {});
    setOpen(!open);
  };

  const entries = [...(stored?.entries || [])].reverse();

  return (
    <div className="usage-badge">
      <button
        ref={buttonRef}
        type="button"
        className="usage-badge__button"
        onClick={toggle}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Token usage of this chat"
      >
        {formatTokenCount(totalTokens)} tokens · {formatTotalCost(totals)}
      </button>

      {open && position && createPortal(
        <div
          ref={popoverRef}
          className="usage-popover"
          role="dialog"
          aria-label="Token usage of this chat"
          style={position}
        >
          <div className="usage-popover__header">
            <span>This chat</span>
            <Link to="/settings?tab=usage" className="usage-popover__link" onClick={() => setOpen(false)}>
              All usage
            </Link>
          </div>
          <UsageSummary totals={totals} />

          {liveTurn && (
            <div className="usage-popover__live">
              In progress · {liveTurn.model} · {formatTokenCount(liveTurn.input_tokens)} in ·{' '}
              {formatTokenCount(liveTurn.output_tokens)} out · {formatCost(liveTurn.estimated_cost_usd)}
            </div>
          )}

          <div className="usage-entry__head">
            <span />
            <span>Task</span>
            <span>In</span>
            <span>Out</span>
            <span>Cost</span>
          </div>
          <ul className="usage-popover__list">
            {entries.map((entry) => <UsageEntry key={entry.id} entry={entry} />)}
            {entries.length === 0 && !liveTurn && (
              <li className="usage-popover__empty">No stored usage yet.</li>
            )}
          </ul>
          <p className="usage-popover__note">
            Input includes cached tokens; output includes reasoning. Costs are estimates from list prices.
          </p>
        </div>,
        document.body,
      )}
    </div>
  );
};

export default UsageBadge;
