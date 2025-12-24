import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';

const ChatList = ({ currentChatId, onClose }) => {
  const navigate = useNavigate();
  const { fetchChats } = useChatStore();
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadChats = async () => {
      try {
        const data = await fetchChats();
        setChats(data);
      } catch (error) {
        console.error("Failed to fetch chats:", error);
      } finally {
        setLoading(false);
      }
    };
    loadChats();
  }, [fetchChats]);

  const handleChatClick = (chatId) => {
    navigate(`/chat/${chatId}`);
    if (onClose) onClose();
  };

  const handleNewChat = () => {
    navigate('/chat/new');
    if (onClose) onClose();
  }

  if (loading) {
    return <div style={{ padding: '1rem', color: '#666' }}>Loading chats...</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: 'transparent' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>Your Chats</h3>
        <button 
            onClick={handleNewChat}
            className="btn btn-primary"
            style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }}
        >
            + New
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {chats.length === 0 ? (
          <div style={{ padding: '2rem 1rem', color: 'var(--text-secondary)', textAlign: 'center', fontSize: '0.9rem' }}>
            No chats yet. Start a new analysis!
          </div>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {chats.map((chat) => (
              <li
                key={chat.id}
                onClick={() => handleChatClick(chat.id)}
                style={{
                  padding: '0.75rem 1rem',
                  cursor: 'pointer',
                  backgroundColor: chat.id === currentChatId ? 'rgba(37, 99, 235, 0.08)' : 'transparent',
                  borderBottom: '1px solid var(--border-color)',
                  transition: 'all 0.2s',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  borderLeft: chat.id === currentChatId ? '3px solid var(--primary-color)' : '3px solid transparent'
                }}
                onMouseEnter={(e) => {
                    if (chat.id !== currentChatId) e.currentTarget.style.backgroundColor = 'var(--background-color)';
                }}
                onMouseLeave={(e) => {
                    if (chat.id !== currentChatId) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', width: '100%' }}>
                    <div style={{ fontWeight: chat.id === currentChatId ? '600' : '500', marginBottom: '0.25rem', color: 'var(--text-primary)' }}>{chat.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {new Date(chat.updated_at).toLocaleDateString()}
                    </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default ChatList;
