import React, { useState } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

const ChatInterface = () => {
  const { messages, sendMessage, isLoading, thinkingMessage, uploadNetwork, chatId } = useChatStore();
  const { nodes } = useNetworkStore();
  const [input, setInput] = useState('');
  const fileInputRef = React.useRef(null);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    await sendMessage(input);
    setInput('');
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (file) {
      await uploadNetwork(chatId, file);
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
      
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {messages.map((msg, idx) => (
          <div key={idx} style={{ 
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            backgroundColor: msg.role === 'user' ? 'var(--primary-color)' : 'var(--border-color)',
            color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
            padding: '0.5rem 1rem',
            borderRadius: '1rem',
            maxWidth: '80%'
          }}>
            {msg.content}
          </div>
        ))}
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
