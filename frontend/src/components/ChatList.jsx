import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';

const ChatList = ({ currentChatId, onClose }) => {
  const navigate = useNavigate();
  const { fetchChats } = useChatStore();
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingChatId, setEditingChatId] = useState(null);
  const [editName, setEditName] = useState("");

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



  const handleEditClick = (e, chat) => {
    e.stopPropagation();
    setEditingChatId(chat.id);
    setEditName(chat.name);
  };

  const handleEditSubmit = async (e) => {
    e.stopPropagation();
    if (editingChatId && editName.trim()) {
      try {
        await useChatStore.getState().renameChat(editingChatId, editName.trim());
        setChats(chats.map(c => c.id === editingChatId ? { ...c, name: editName.trim() } : c));
        setEditingChatId(null);
      } catch (error) {
        console.error("Failed to rename chat:", error);
      }
    }
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter') {
        handleEditSubmit(e);
    } else if (e.key === 'Escape') {
        setEditingChatId(null);
    }
  };

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
                  borderLeft: chat.id === currentChatId ? '3px solid var(--primary-color)' : '3px solid transparent',
                  position: 'relative' // For absolute positioning if needed, or just flex context
                }}
                onMouseEnter={(e) => {
                    if (chat.id !== currentChatId) e.currentTarget.style.backgroundColor = 'var(--background-color)';
                    // Show edit button
                    const editBtn = e.currentTarget.querySelector('.edit-btn');
                    if (editBtn) editBtn.style.opacity = '1';
                }}
                onMouseLeave={(e) => {
                    if (chat.id !== currentChatId) e.currentTarget.style.backgroundColor = 'transparent';
                    // Hide edit button
                    const editBtn = e.currentTarget.querySelector('.edit-btn');
                    if (editBtn) editBtn.style.opacity = '0';
                }}
              >
                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    {editingChatId === chat.id ? (
                        <input 
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            onKeyDown={handleEditKeyDown}
                            onClick={(e) => e.stopPropagation()}
                            onBlur={() => setEditingChatId(null)}
                            autoFocus
                            style={{
                                width: '100%',
                                padding: '0.25rem',
                                border: '1px solid var(--primary-color)',
                                borderRadius: '4px',
                                outline: 'none'
                            }}
                        />
                    ) : (
                        <>
                            <div style={{ overflow: 'hidden', flex: 1 }}>
                                <div style={{ fontWeight: chat.id === currentChatId ? '600' : '500', marginBottom: '0.25rem', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{chat.name}</div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    {new Date(chat.updated_at).toLocaleDateString()}
                                </div>
                            </div>
                            <button
                                className="edit-btn"
                                onClick={(e) => handleEditClick(e, chat)}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    opacity: 0,
                                    transition: 'opacity 0.2s',
                                    padding: '0.25rem',
                                    marginLeft: '0.5rem',
                                    color: 'var(--text-secondary)'
                                }}
                                title="Rename chat"
                            >
                                ✏️
                            </button>
                        </>
                    )}
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
