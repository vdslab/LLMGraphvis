import { useRef, useEffect } from 'react';
import { ArrowUp, Paperclip, X } from 'lucide-react';

const MAX_HEIGHT = 160;

/**
 * The message box.
 *
 * It stays enabled while a turn is running. The backend accepts a message and
 * answers 202 immediately, and a chat is a queue rather than a lock, so making
 * the user wait for the previous answer before they may even type was a
 * restriction the system never needed. Anything sent mid-turn is held by the
 * store and dispatched when the turn ends — see `chatStore.sendMessage`.
 */
const Composer = ({
  value,
  onChange,
  onSubmit,
  onAttach,
  contextNode,
  onCancelContext,
  queuedCount,
  busy,
}) => {
  const textareaRef = useRef(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  const handleKeyDown = (event) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    if (event.nativeEvent.isComposing) return;
    event.preventDefault();
    onSubmit(event);
  };

  return (
    <form className="composer" onSubmit={onSubmit}>
      {contextNode && (
        <div className="composer__context">
          <span className="composer__context-label">
            Node <strong>{contextNode.label}</strong>
          </span>
          <button
            type="button"
            onClick={onCancelContext}
            className="composer__context-clear"
            title="Remove context"
          >
            <X size={13} aria-hidden />
          </button>
        </div>
      )}

      {queuedCount > 0 && (
        <div className="composer__queued">
          {queuedCount} message{queuedCount > 1 ? 's' : ''} waiting for the current
          turn to finish
        </div>
      )}

      <div className="composer__row">
        {onAttach && (
          <button
            type="button"
            className="composer__icon-btn"
            onClick={onAttach}
            title="Upload GraphML"
          >
            <Paperclip size={16} aria-hidden />
          </button>
        )}
        <textarea
          ref={textareaRef}
          className="composer__input"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={busy ? 'Add another message…' : 'Ask about this network…'}
          rows={1}
        />
        <button
          type="submit"
          className="composer__send"
          disabled={!value.trim()}
          title="Send"
        >
          <ArrowUp size={16} aria-hidden />
        </button>
      </div>
    </form>
  );
};

export default Composer;
