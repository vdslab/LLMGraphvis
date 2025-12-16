import React, { useState } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const ChatInterface = ({ selectedNode }) => {
  const { messages, sendMessage, isLoading, thinkingMessage, uploadNetwork, chatId } = useChatStore();
  const { nodes } = useNetworkStore();
  const [input, setInput] = useState('');
  const fileInputRef = React.useRef(null);

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
          // Parse <thought> tags (handle both complete and streaming/incomplete tags)
          const parts = msg.content.split(/(<thought>[\s\S]*?(?:<\/thought>|$))/g);
          
          return (
            <div key={idx} style={{ 
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              backgroundColor: msg.role === 'user' ? 'var(--primary-color)' : 'var(--border-color)',
              color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
              padding: '0.5rem 1rem',
              borderRadius: '1rem',
              maxWidth: '80%'
            }}>
              {parts.map((part, partIdx) => {
                if (part.startsWith('<thought>')) {
                  const thoughtContent = part.replace(/<\/?thought>/g, '').trim();
                  if (!thoughtContent) return null;
                  
                  return (
                    <details key={partIdx} open={part.includes('</thought>') ? false : true} style={{ marginBottom: '0.5rem', opacity: 0.8 }}>
                      <summary style={{ 
                        cursor: 'pointer', 
                        fontSize: '0.8rem', 
                        color: msg.role === 'user' ? 'rgba(255,255,255,0.7)' : '#666',
                        userSelect: 'none'
                      }}>
                        Thinking Process {part.includes('</thought>') ? '' : '(Thinking...)'}
                      </summary>
                      <div style={{ 
                        fontSize: '0.85rem', 
                        fontStyle: 'italic', 
                        marginTop: '0.25rem',
                        paddingLeft: '0.5rem',
                        borderLeft: msg.role === 'user' ? '2px solid rgba(255,255,255,0.3)' : '2px solid #ccc',
                        whiteSpace: 'pre-wrap'
                      }}>
                        {thoughtContent}
                      </div>
                    </details>
                  );
                }
                
                if (!part.trim()) return null;
                
                return (
                  <ReactMarkdown key={partIdx} remarkPlugins={[remarkGfm]}>
                    {part}
                  </ReactMarkdown>
                );
              })}
            </div>
          );
        })}
        {isLoading && (
          <div style={{ alignSelf: 'flex-start', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            {thinkingMessage || "Thinking..."}
          </div>
        )}
      </div>
      
      <form onSubmit={handleSend} style={{ padding: '1rem', borderTop: '1px solid var(--border-color)', display: 'flex', gap: '0.5rem' }}>
        <input
          type="text"
          className="input"
          style={{ flex: 1 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message..."
          disabled={isLoading}
        />
        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatInterface;
