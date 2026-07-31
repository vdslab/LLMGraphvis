import { useMemo } from 'react';
import { Brain, ListChecks, Clock, AlertCircle, RotateCw } from 'lucide-react';
import { parseMessageContent } from '../../utils/parseMessageContent';
import Disclosure from './Disclosure';
import ToolCall from './ToolCall';
import Markdown from './Markdown';

/**
 * Tool calls this message made but did not place inline.
 *
 * Markers are emitted as the turn streams; a message reloaded from the database
 * has the executions but the markers too, so this only fires for the legacy
 * `meta_data` shape and for turns whose markers were lost.
 */
const legacyExecutions = (metaData) => {
  if (!metaData) return [];
  const steps = Array.isArray(metaData) ? metaData : metaData.steps || [];
  return steps.flatMap((step) =>
    (step.tool_calls || []).map((call) => ({
      tool_name: call.name,
      status: call.status,
      arguments: call.args,
    })),
  );
};

const ThoughtBlock = ({ block }) => (
  <Disclosure
    icon={<Brain size={13} aria-hidden />}
    label="Thinking"
    tone="thought"
    forceOpen={!block.complete}
  >
    <pre className="thought__text">{block.content}</pre>
  </Disclosure>
);

const StepsBlock = ({ block }) => (
  <Disclosure
    icon={<ListChecks size={13} aria-hidden />}
    label="Steps"
    meta={`${block.steps.length}`}
    tone="steps"
  >
    <ol className="steps__list">
      {block.steps.map((step, idx) => (
        <li key={idx}>{step}</li>
      ))}
    </ol>
  </Disclosure>
);

const ChatMessage = ({ message, onRetry }) => {
  const blocks = useMemo(
    () => parseMessageContent(message.content),
    [message.content],
  );

  const executions = message.tool_executions || [];
  const inlineToolIndexes = new Set(
    blocks.filter((b) => b.type === 'tool').map((b) => b.index),
  );
  const orphanExecutions = [
    ...executions.filter((_, idx) => !inlineToolIndexes.has(idx)),
    ...(executions.length ? [] : legacyExecutions(message.meta_data)),
  ];

  if (message.role === 'user') {
    return (
      <div className={`msg msg--user msg--${message.status || 'sent'}`}>
        <div className="bubble bubble--user">{message.content}</div>
        <div className="msg__footnote">
          {message.status === 'queued' && (
            <span className="msg__state">
              <Clock size={11} aria-hidden /> Queued
            </span>
          )}
          {message.status === 'sending' && (
            <span className="msg__state">Sending…</span>
          )}
          {message.status === 'failed' && (
            <>
              <span className="msg__state msg__state--error">
                <AlertCircle size={11} aria-hidden /> Not sent
              </span>
              <button
                type="button"
                className="msg__retry"
                onClick={() => onRetry?.(message)}
              >
                <RotateCw size={11} aria-hidden /> Retry
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="msg msg--assistant">
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'thought':
            return <ThoughtBlock key={idx} block={block} />;
          case 'steps':
            return <StepsBlock key={idx} block={block} />;
          case 'collapsible':
            return (
              <Disclosure
                key={idx}
                label={block.title}
                tone="section"
                defaultOpen={block.open}
              >
                <Markdown>{block.content}</Markdown>
              </Disclosure>
            );
          case 'tool': {
            // A marker whose record has not arrived yet. Rare now that early
            // results are buffered (see chatStore.pendingToolExecutions), but
            // the marker must still render as *something* placed correctly.
            const execution = executions[block.index] || {
              tool_name: 'Tool call',
              status: 'running',
            };
            return <ToolCall key={idx} execution={execution} />;
          }
          default:
            return (
              <div key={idx} className="bubble bubble--assistant">
                <Markdown>{block.content}</Markdown>
              </div>
            );
        }
      })}

      {orphanExecutions.length > 0 && (
        <Disclosure
          label="Actions"
          meta={`${orphanExecutions.length}`}
          tone="section"
        >
          {orphanExecutions.map((execution, idx) => (
            <ToolCall key={idx} execution={execution} />
          ))}
        </Disclosure>
      )}
    </div>
  );
};

export default ChatMessage;
