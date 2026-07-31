import { useRef, useState, useEffect, useCallback } from 'react';
import { ArrowDown } from 'lucide-react';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';
import UsageBadge from './UsageBadge';
import ModelSelector from './ModelSelector';
import ChatMessage from './chat/ChatMessage';
import TurnStatus from './chat/TurnStatus';
import Composer from './chat/Composer';
import './chat/chat.css';

// How far from the bottom still counts as "following the conversation".
const AT_BOTTOM_PX = 60;
const SHOW_JUMP_PX = 140;

const ChatInterface = ({ contextNode, onMessageSent, onCancelContext }) => {
  const {
    messages,
    sendMessage,
    retryMessage,
    isLoading,
    thinkingMessage,
    progressSteps,
    runningTool,
    uploadNetwork,
    chatId,
  } = useChatStore();
  const { nodes } = useNetworkStore();

  const [input, setInput] = useState('');
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);
  const isAtBottomRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior });
  }, []);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    isAtBottomRef.current = distance < AT_BOTTOM_PX;
    setShowJump(distance > SHOW_JUMP_PX);
  };

  // Follow new content only while the user is already at the bottom — reading
  // back through a long turn should not be interrupted by the agent's output.
  // Their own message is the exception; sending it is a request to see it.
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (isAtBottomRef.current || last?.role === 'user') scrollToBottom();
  }, [messages, thinkingMessage, progressSteps, runningTool, isLoading, scrollToBottom]);

  const handleSend = async (event) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;

    const content = contextNode
      ? `${trimmed}\n\n[Context: User selected node ID: '${contextNode.id}', Label: '${contextNode.label}']`
      : trimmed;

    // Clear the box first: the message is already on screen by the time the
    // request is in flight, and a composer that empties on Enter is the whole
    // point of not blocking on the turn.
    setInput('');
    onMessageSent?.();
    sendMessage(content);
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      await uploadNetwork(chatId, file);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      event.target.value = '';
    }
  };

  const queuedCount = messages.filter((m) => m.status === 'queued').length;

  return (
    <div className="chat">
      <div className="chat__header">
        <h3 className="chat__title">Chat</h3>
        <div className="chat__header-actions">
          <ModelSelector />
          <UsageBadge />
        </div>
      </div>

      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileUpload}
        accept=".graphml,.xml"
      />

      <div className="chat__body">
        <div className="chat__scroll" ref={scrollRef} onScroll={handleScroll}>
          {messages.length === 0 && !isLoading && (
            <div className="chat__empty">
              {nodes.length > 0
                ? 'Ask about this network — its communities, its central nodes, or how it should be drawn.'
                : 'Upload a GraphML file to get started.'}
            </div>
          )}

          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} onRetry={retryMessage} />
          ))}

          <TurnStatus
            isLoading={isLoading}
            progressSteps={progressSteps}
            runningTool={runningTool}
            thinkingMessage={thinkingMessage}
          />
        </div>

        {showJump && (
          <button
            type="button"
            className="chat__jump"
            onClick={() => scrollToBottom()}
            title="Jump to latest"
          >
            <ArrowDown size={14} aria-hidden />
          </button>
        )}
      </div>

      <Composer
        value={input}
        onChange={setInput}
        onSubmit={handleSend}
        onAttach={nodes.length > 0 ? () => fileInputRef.current?.click() : null}
        contextNode={contextNode}
        onCancelContext={onCancelContext}
        queuedCount={queuedCount}
        busy={isLoading}
      />
    </div>
  );
};

export default ChatInterface;
