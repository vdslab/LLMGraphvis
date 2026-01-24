import React, { useState } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import remarkColorPreview from '../utils/remarkColorPreview';

const ChatInterface = ({ contextNode, onMessageSent, onCancelContext }) => {
  const { messages, sendMessage, isLoading, thinkingMessage, uploadNetwork, chatId } = useChatStore();
  const { nodes } = useNetworkStore();
  const [input, setInput] = useState('');
  const fileInputRef = React.useRef(null);
  const textareaRef = React.useRef(null);
  
  // Scroll refs
  const scrollRef = React.useRef(null);
  const isAtBottomRef = React.useRef(true); // Default to true so first load scrolls down
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  // Helper to scroll to bottom
  const scrollToBottom = (behavior = 'auto') => {
    if (scrollRef.current) {
        scrollRef.current.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: behavior
        });
    }
  };

  // Handle scroll events to update tracking refs and button visibility
  const handleScroll = () => {
    if (!scrollRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    
    // Threshold for "at bottom" (e.g. 50px)
    const isAtBottom = distanceFromBottom < 50;
    isAtBottomRef.current = isAtBottom;
    
    // Show button if we are far from bottom (e.g. > 100px)
    setShowScrollBottom(distanceFromBottom > 100);
  };

  // Auto-scroll effect
  React.useEffect(() => {
    // If we are "at bottom", keep scrolling down as content comes in.
    // Also scroll down if it's the very first load (implied by isAtBottomRef default true)
    // Or if a new user message was just added (we might need a flag for that, but usually user message implies desire to see it)
    
    // Check if the last message is from user -> Force scroll
    const lastMsg = messages[messages.length - 1];
    const isLastMsgUser = lastMsg?.role === 'user';

    if (isAtBottomRef.current || isLastMsgUser) {
        scrollToBottom('smooth');
    }
  }, [messages, thinkingMessage, isLoading]);

  // Auto-resize textarea
  React.useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [input]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    let content = input;
    if (contextNode) {
      content += `\n\n[Context: User selected node ID: '${contextNode.id}', Label: '${contextNode.label}']`;
    }

    await sendMessage(content);
    setInput('');
    // Force scroll to bottom immediately when sending
    // Use setTimeout to ensure state update has likely triggered render or just to be safe async
    setTimeout(() => scrollToBottom('smooth'), 0);
    if (onMessageSent) onMessageSent();
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (file) {
      try {
        await uploadNetwork(chatId, file);
      } catch (error) {
        console.error("Upload failed:", error);
        alert("Failed to upload file. Please try again.");
      }
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
        <h3>Chat</h3>
        {nodes.length > 0 && (
          <>
            <input 
              type="file" 
              ref={fileInputRef} 
              style={{ display: 'none' }} 
              onChange={handleFileUpload} 
              accept=".graphml,.xml"
            />
            <button className="btn" onClick={() => fileInputRef.current.click()}>
              Upload GraphML
            </button>
          </>
        )}
      </div>
      
      {contextNode && (
        <div style={{ 
          padding: '0.5rem 1rem', 
          backgroundColor: '#e3f2fd', 
          borderBottom: '1px solid var(--border-color)',
          fontSize: '0.9rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>Context: <strong>{contextNode.label}</strong> (ID: {contextNode.id})</span>
          <button 
            onClick={onCancelContext}
            style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '1.2rem',
                color: '#666',
                padding: '0 0.5rem'
            }}
            title="Remove context"
          >
            ×
          </button>
        </div>
      )}
      
      
    <div 
        ref={scrollRef}
        onScroll={handleScroll}
        style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', position: 'relative' }}
    >
        {messages.map((msg, idx) => {
          // Parse <thought> tags
          const parts = msg.content.split(/(<thought>[\s\S]*?(?:<\/thought>|$))/g);
          
          return (
            <div key={idx} style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}>
              {parts.map((part, partIdx) => {
                const isThought = part.startsWith('<thought>');
                const cleanPart = isThought ? part.replace(/<\/?thought>/g, '').trim() : part.trim();
                
                if (!cleanPart) return null;

                if (isThought) {
                  return (
                    <details 
                      key={partIdx} 
                      open={false}
                      style={{ 
                        marginBottom: '0.5rem', 
                        maxWidth: '100%',
                        width: '100%' 
                      }}
                    >
                      <summary style={{ 
                        cursor: 'pointer', 
                        fontSize: '0.75rem', 
                        color: '#888',
                        userSelect: 'none',
                        fontStyle: 'italic'
                      }}>
                        Thinking Process {part.includes('</thought>') ? '' : '(Thinking...)'}
                      </summary>
                      <div style={{ 
                        fontSize: '0.8rem', 
                        color: '#666',
                        marginTop: '0.25rem',
                        padding: '0.5rem',
                        backgroundColor: '#f5f5f5',
                        borderRadius: '4px',
                        whiteSpace: 'pre-wrap',
                        borderLeft: '3px solid #ddd'
                      }}>
                        {cleanPart}
                      </div>
                    </details>
                  );
                }
                
                // Tool Execution Logs (Persistent)
                let toolLogsRender = null;
                
                // 1. New Schema: tool_executions
                if (msg.tool_executions && msg.tool_executions.length > 0) {
                     const logs = msg.tool_executions.map((tc, idx) => {
                        let durationStr = "";
                        if (tc.started_at && tc.completed_at) {
                            const start = new Date(tc.started_at);
                            const end = new Date(tc.completed_at);
                            const diff = end - start;
                            durationStr = diff < 1000 ? `${diff}ms` : `${(diff/1000).toFixed(2)}s`;
                        }

                        return (
                                <div key={`exec-${idx}`} style={{
                                    marginTop: '0.5rem',
                                    marginBottom: '0.5rem',
                                    padding: '0.5rem',
                                    backgroundColor: 'rgba(0, 0, 0, 0.03)',
                                    borderRadius: '4px',
                                    borderLeft: `3px solid ${tc.status === 'failed' ? '#ff5252' : '#4caf50'}`,
                                    fontSize: '0.85rem',
                                    fontFamily: 'monospace'
                                }}>
                                    <div style={{ fontWeight: 'bold', display: 'flex', justifyContent: 'space-between' }}>
                                        <span>🛠️ {tc.tool_name}</span>
                                        <span style={{ 
                                            display: 'flex', gap: '8px', alignItems: 'center'
                                        }}>
                                            {durationStr && <span style={{color: '#888', fontSize: '0.7rem'}}>⏱️ {durationStr}</span>}
                                            <span style={{ 
                                                color: tc.status === 'failed' ? '#d32f2f' : '#2e7d32',
                                                textTransform: 'uppercase',
                                                fontSize: '0.7rem'
                                            }}>
                                                {tc.status || 'COMPLETED'}
                                            </span>
                                        </span>
                                    </div>
                                    {tc.thought && (
                                         <div style={{ fontStyle: 'italic', color: '#555', marginBottom: '4px', fontSize: '0.8rem' }}>
                                            "{tc.thought}"
                                         </div>
                                    )}
                                    <div style={{ color: '#666', marginTop: '0.25rem', fontSize: '0.75rem' }}>
                                        Args: {JSON.stringify(tc.arguments).slice(0, 100)}{JSON.stringify(tc.arguments).length > 100 ? '...' : ''}
                                    </div>
                                    {tc.error && (
                                        <div style={{ color: '#d32f2f', marginTop: '0.25rem' }}>
                                            Error: {tc.error}
                                        </div>
                                    )}
                                </div>
                        );
                     });
                     
                     toolLogsRender = (
                        <details key="tool-logs-new" style={{ width: '100%', marginBottom: '0.5rem' }}>
                            <summary style={{ cursor: 'pointer', fontSize: '0.8rem', color: '#666', userSelect: 'none' }}>
                                View Action Log ({logs.length} actions)
                            </summary>
                            <div style={{ marginTop: '0.5rem' }}>
                                {logs}
                            </div>
                        </details>
                     );

                // 2. Legacy Schema: meta_data
                } else if (msg.meta_data) {
                    let steps = [];
                    // Handle both array (new format) and object (legacy/future-proof)
                    if (Array.isArray(msg.meta_data)) {
                        steps = msg.meta_data;
                    } else if (msg.meta_data.steps) {
                        steps = msg.meta_data.steps;
                    }

                    if (steps.length > 0) {
                        const toolLogs = steps.flatMap((step, stepIdx) => {
                            if (!step.tool_calls) return [];
                            return step.tool_calls.map((tc, tcIdx) => (
                                <div key={`tool-${stepIdx}-${tcIdx}`} style={{
                                    marginTop: '0.5rem',
                                    marginBottom: '0.5rem',
                                    padding: '0.5rem',
                                    backgroundColor: 'rgba(0, 0, 0, 0.03)',
                                    borderRadius: '4px',
                                    borderLeft: `3px solid ${tc.status === 'failed' ? '#ff5252' : '#4caf50'}`,
                                    fontSize: '0.85rem',
                                    fontFamily: 'monospace'
                                }}>
                                    <div style={{ fontWeight: 'bold', display: 'flex', justifyContent: 'space-between' }}>
                                        <span>🛠️ {tc.name}</span>
                                        <span style={{ 
                                            color: tc.status === 'failed' ? '#d32f2f' : '#2e7d32',
                                            textTransform: 'uppercase',
                                            fontSize: '0.7rem'
                                        }}>
                                            {tc.status || 'COMPLETED'}
                                        </span>
                                    </div>
                                    <div style={{ color: '#666', marginTop: '0.25rem', fontSize: '0.75rem' }}>
                                        Running with args: {JSON.stringify(tc.args).slice(0, 100)}{JSON.stringify(tc.args).length > 100 ? '...' : ''}
                                    </div>
                                    {tc.error && (
                                        <div style={{ color: '#d32f2f', marginTop: '0.25rem' }}>
                                            Error: {typeof tc.error === 'string' ? tc.error : JSON.stringify(tc.error)}
                                        </div>
                                    )}
                                </div>
                            ));
                        });

                        if (toolLogs.length > 0) {
                            toolLogsRender = (
                                <details key="tool-logs" style={{ width: '100%', marginBottom: '0.5rem' }}>
                                    <summary style={{ cursor: 'pointer', fontSize: '0.8rem', color: '#666', userSelect: 'none' }}>
                                        View Action Log ({toolLogs.length} actions)
                                    </summary>
                                    <div style={{ marginTop: '0.5rem' }}>
                                        {toolLogs}
                                    </div>
                                </details>
                            );
                        }
                    }
                }
                
                if (toolLogsRender) {
                    parts.push(toolLogsRender);
                }

                // Regular message bubble
                return (
                  <div key={partIdx} style={{ 
                    backgroundColor: msg.role === 'user' ? 'var(--primary-color)' : 'var(--border-color)',
                    color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
                    padding: '0.75rem 1rem',
                    borderRadius: '1rem',
                    borderTopLeftRadius: msg.role === 'user' ? '1rem' : '0',
                    borderTopRightRadius: msg.role === 'user' ? '0' : '1rem',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
                  }}>
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm, remarkBreaks, remarkColorPreview]}
                      components={{
                        a: ({node, href, children, ...props}) => {
                          if (href === '#color-preview') {
                            const color = node.data?.hProperties?.['data-color'] || children.toString(); // Fallback
                            return (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                <span style={{
                                  display: 'inline-block',
                                  width: '12px',
                                  height: '12px',
                                  backgroundColor: color,
                                  border: '1px solid #ccc',
                                  borderRadius: '2px',
                                  flexShrink: 0
                                }}></span>
                                {children}
                              </span>
                            );
                          }
                          return <a href={href} {...props} target="_blank" rel="noopener noreferrer">{children}</a>;
                        }
                      }}
                    >
                      {cleanPart}
                    </ReactMarkdown>
                  </div>
                );
              })}
            </div>
          );
        })}
        {isLoading && (
          <div style={{ alignSelf: 'flex-start', color: 'var(--text-secondary)', fontSize: '0.8rem', fontStyle: 'italic', marginLeft: '1rem' }}>
             {thinkingMessage || "Thinking..."}
          </div>
        )}

        
        {/* Scroll to Bottom Button */}
        {showScrollBottom && (
            <button
                onClick={() => scrollToBottom('smooth')}
                style={{
                    position: 'sticky',
                    bottom: '20px',
                    alignSelf: 'flex-end',
                    marginRight: '1rem',
                    backgroundColor: 'var(--primary-color)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '50%',
                    width: '4rem',
                    height: '4rem',
                    fontSize: '1.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                    zIndex: 10,
                    marginTop: '-4rem', // Negative margin to overlay on content if needed, or just let it float
                    marginBottom: '0', // Reset
                    opacity: 0.9,
                    transition: 'opacity 0.2s'
                }}
                title="Scroll to bottom"
            >
                ↓
            </button>
        )}
      </div>
      
      <form onSubmit={handleSend} style={{ padding: '1rem', borderTop: '1px solid var(--border-color)', display: 'flex', gap: '0.5rem' }}>
        <textarea
          ref={textareaRef}
          className="input"
          style={{ 
            flex: 1, 
            resize: 'none', 
            minHeight: '42px', 
            maxHeight: '150px',
            fontFamily: 'inherit',
            lineHeight: '1.5',
            paddingTop: '10px',
            paddingBottom: '10px'
          }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              if (e.nativeEvent.isComposing) return;
              e.preventDefault();
              handleSend(e);
            }
          }}
          placeholder="Type a message..."
          disabled={isLoading}
          rows={1}
        />
        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatInterface;
