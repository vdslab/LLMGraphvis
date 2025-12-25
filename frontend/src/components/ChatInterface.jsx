import React, { useState } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

const ChatInterface = ({ selectedNode }) => {
  const { messages, sendMessage, isLoading, thinkingMessage, uploadNetwork, chatId } = useChatStore();
  const { nodes } = useNetworkStore();
  const [input, setInput] = useState('');
  const fileInputRef = React.useRef(null);
  const textareaRef = React.useRef(null);

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
    if (selectedNode) {
      content += `\n\n[Context: User selected node ID: '${selectedNode.id}', Label: '${selectedNode.label}']`;
    }

    await sendMessage(content);
    setInput('');
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
      
      {selectedNode && (
        <div style={{ 
          padding: '0.5rem 1rem', 
          backgroundColor: '#e3f2fd', 
          borderBottom: '1px solid var(--border-color)',
          fontSize: '0.9rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>Context: <strong>{selectedNode.label}</strong> (ID: {selectedNode.id})</span>
        </div>
      )}
      
    <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
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
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
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
