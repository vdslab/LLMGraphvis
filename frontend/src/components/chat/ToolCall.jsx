import { useState } from 'react';
import { Wrench, Check, X, Loader2, Brain } from 'lucide-react';
import { parseMessageContent } from '../../utils/parseMessageContent';
import Disclosure from './Disclosure';

const formatDuration = (startedAt, completedAt) => {
  if (!startedAt || !completedAt) return null;
  const ms = new Date(completedAt) - new Date(startedAt);
  if (Number.isNaN(ms) || ms < 0) return null;
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
};

const formatArgs = (args) => {
  if (args == null) return null;
  if (typeof args === 'string') return args;
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
};

// `analysis_detect_communities` does not fit one line of a narrow panel, and an
// underscore is not a break opportunity, so the browser splits it mid-word.
// Marking each underscore as one keeps the name whole and readable.
const breakable = (name) => (name || '').replace(/_/g, '_​');

// Older OpenAI-compatible responses stored the complete textual protocol in
// ToolExecution.thought, including the literal <thought> wrapper. Newer/native
// providers store only its body. Accept both shapes so existing chats render
// the same as new ones.
const thoughtBody = (thought) => {
  if (!thought) return '';
  const blocks = parseMessageContent(String(thought));
  const taggedThoughts = blocks
    .filter((block) => block.type === 'thought')
    .map((block) => block.content)
    .filter(Boolean);
  return taggedThoughts.length ? taggedThoughts.join('\n\n') : String(thought).trim();
};

const STATUS_ICON = {
  failed: <X size={12} aria-hidden />,
  running: <Loader2 size={12} className="spin" aria-hidden />,
  completed: <Check size={12} aria-hidden />,
};

/**
 * One MCP tool call: what ran, whether it worked, and — on demand — with what.
 *
 * Deliberately a single line until opened. A turn routinely makes four or five
 * calls, and in a panel this narrow an always-expanded argument dump pushes the
 * agent's actual answer off the screen.
 */
const ToolCall = ({ execution }) => {
  const [showArgs, setShowArgs] = useState(false);

  const status = execution.status || 'completed';
  const duration = formatDuration(execution.started_at, execution.completed_at);
  const args = formatArgs(execution.arguments);
  const thought = thoughtBody(execution.thought);

  return (
    <div className={`toolcall toolcall--${status}`}>
      <div className="toolcall__head">
        <Wrench size={12} className="toolcall__tool-icon" aria-hidden />
        <span className="toolcall__name" title={execution.tool_name}>
          {breakable(execution.tool_name)}
        </span>
        {duration && <span className="toolcall__duration">{duration}</span>}
        <span className={`toolcall__status toolcall__status--${status}`}>
          {STATUS_ICON[status] || STATUS_ICON.completed}
        </span>
      </div>

      {thought && (
        <div className="toolcall__thought">
          <Disclosure
            icon={<Brain size={13} aria-hidden />}
            label="Thinking"
            tone="thought"
          >
            <pre className="thought__text">{thought}</pre>
          </Disclosure>
        </div>
      )}

      {execution.error && <p className="toolcall__error">{execution.error}</p>}

      {args && (
        <>
          <button
            type="button"
            className="toolcall__toggle"
            onClick={() => setShowArgs((open) => !open)}
          >
            {showArgs ? 'Hide arguments' : 'Arguments'}
          </button>
          {showArgs && <pre className="toolcall__args">{args}</pre>}
        </>
      )}
    </div>
  );
};

export default ToolCall;
