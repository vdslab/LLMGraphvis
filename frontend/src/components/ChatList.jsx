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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: '#f8f9fa' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Your Chats</h3>
        <button 
            onClick={handleNewChat}
            className="btn btn-primary"
            style={{ padding: '4px 8px', fontSize: '0.8rem' }}
        >
            + New
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {chats.length === 0 ? (
          <div style={{ padding: '1rem', color: '#999', textAlign: 'center' }}>No chats yet.</div>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {chats.map((chat) => (
              <li
                key={chat.id}
                onClick={() => handleChatClick(chat.id)}
                style={{
                  padding: '10px 1rem',
                  cursor: 'pointer',
                  backgroundColor: chat.id === currentChatId ? '#e3f2fd' : 'transparent',
                  borderBottom: '1px solid #eee',
                  transition: 'background-color 0.2s',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
                onMouseEnter={(e) => {
                    if (chat.id !== currentChatId) e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
                onMouseLeave={(e) => {
                    if (chat.id !== currentChatId) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <div style={{ fontWeight: '500', marginBottom: '2px' }}>{chat.name}</div>
                    <div style={{ fontSize: '0.75rem', color: '#888' }}>
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
