import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';
import { Plus, Edit2, MessageSquare } from 'lucide-react';

const ChatList = ({ currentChatId, onClose }) => {
  const navigate = useNavigate();
  const { fetchChats } = useChatStore();
  // The open chat can be renamed while this list is mounted (auto-naming arrives
  // over SSE), so track the store's copy of its name rather than only the fetch.
  const chatName = useChatStore((state) => state.chatName);
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingChatId, setEditingChatId] = useState(null);
  const [editName, setEditName] = useState('');

  useEffect(() => {
    const loadChats = async () => {
      try {
        const data = await fetchChats();
        setChats(data);
      } catch (error) {
        console.error('Failed to fetch chats:', error);
      } finally {
        setLoading(false);
      }
    };
    loadChats();
  }, [fetchChats]);

  useEffect(() => {
    if (!chatName || !currentChatId) return;
    setChats((prev) =>
      prev.map((c) => (c.id === currentChatId ? { ...c, name: chatName } : c))
    );
  }, [chatName, currentChatId]);

  const handleChatClick = (chatId) => {
    navigate(`/chat/${chatId}`);
    if (onClose) onClose();
  };

  const handleNewChat = () => {
    navigate('/chat/new');
    if (onClose) onClose();
  };

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
        setChats(
          chats.map((c) =>
            c.id === editingChatId ? { ...c, name: editName.trim() } : c
          )
        );
        setEditingChatId(null);
      } catch (error) {
        console.error('Failed to rename chat:', error);
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
    return (
      <div
        style={{
          padding: '1.5rem',
          color: 'var(--md-sys-color-on-surface-variant)',
          fontSize: '0.875rem',
          textAlign: 'center',
        }}
      >
        Loading analyses...
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'transparent',
      }}
    >
      <div
        style={{
          padding: '0.875rem 1.25rem',
          borderBottom: '1px solid var(--md-sys-color-outline-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h3
          style={{
            margin: 0,
            fontSize: '0.9375rem',
            fontWeight: 700,
            color: 'var(--md-sys-color-on-surface)',
          }}
        >
          Your Chats
        </h3>
        <button
          onClick={handleNewChat}
          className="btn btn-secondary"
          style={{
            padding: '0.3125rem 0.75rem',
            fontSize: '0.75rem',
            gap: '0.25rem',
          }}
        >
          <Plus size={13} strokeWidth={2.5} />
          <span>New</span>
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
        {chats.length === 0 ? (
          <div
            style={{
              padding: '2.5rem 1rem',
              color: 'var(--md-sys-color-on-surface-variant)',
              textAlign: 'center',
              fontSize: '0.875rem',
            }}
          >
            No chats yet. Start a new analysis!
          </div>
        ) : (
          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              margin: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: '0.25rem',
            }}
          >
            {chats.map((chat) => {
              const isActive = chat.id === currentChatId;
              return (
                <li
                  key={chat.id}
                  onClick={() => handleChatClick(chat.id)}
                  style={{
                    padding: '0.625rem 0.875rem',
                    cursor: 'pointer',
                    borderRadius: 'var(--md-sys-shape-md)',
                    backgroundColor: isActive
                      ? 'var(--md-sys-color-secondary-container)'
                      : 'transparent',
                    color: isActive
                      ? 'var(--md-sys-color-on-secondary-container)'
                      : 'var(--md-sys-color-on-surface)',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.625rem',
                    position: 'relative',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor =
                        'var(--md-sys-color-surface-container)';
                    }
                    const editBtn = e.currentTarget.querySelector('.edit-btn');
                    if (editBtn) editBtn.style.opacity = '1';
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }
                    const editBtn = e.currentTarget.querySelector('.edit-btn');
                    if (editBtn) editBtn.style.opacity = '0';
                  }}
                >
                  <MessageSquare
                    size={16}
                    style={{
                      flexShrink: 0,
                      color: isActive
                        ? 'var(--md-sys-color-primary)'
                        : 'var(--md-sys-color-outline)',
                    }}
                  />
                  <div
                    style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      flex: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      minWidth: 0,
                    }}
                  >
                    {editingChatId === chat.id ? (
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onKeyDown={handleEditKeyDown}
                        onClick={(e) => e.stopPropagation()}
                        onBlur={() => setEditingChatId(null)}
                        autoFocus
                        className="input"
                        style={{
                          width: '100%',
                          padding: '0.25rem 0.5rem',
                          fontSize: '0.8125rem',
                          borderRadius: 'var(--md-sys-shape-sm)',
                        }}
                      />
                    ) : (
                      <>
                        <div style={{ overflow: 'hidden', flex: 1, minWidth: 0 }}>
                          <div
                            style={{
                              fontWeight: isActive ? 700 : 500,
                              fontSize: '0.84375rem',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              lineHeight: 1.3,
                            }}
                          >
                            {chat.name}
                          </div>
                          <div
                            style={{
                              fontSize: '0.6875rem',
                              color: isActive
                                ? 'var(--md-sys-color-secondary)'
                                : 'var(--md-sys-color-outline)',
                              marginTop: '2px',
                            }}
                          >
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
                            transition: 'opacity 0.15s ease',
                            padding: '0.25rem',
                            marginLeft: '0.375rem',
                            color: 'var(--md-sys-color-on-surface-variant)',
                            display: 'flex',
                            alignItems: 'center',
                            borderRadius: 'var(--md-sys-shape-xs)',
                          }}
                          title="Rename chat"
                        >
                          <Edit2 size={13} />
                        </button>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};

export default ChatList;
