import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';
import { useAuthStore } from '../stores/authStore';
import { useNetworkRealtime } from '../hooks/useNetworkRealtime';
import NetworkGraph from '../components/NetworkGraph';
import ChatInterface from '../components/ChatInterface';
import NodeDetailsPanel from '../components/NodeDetailsPanel';
import ChatList from '../components/ChatList';

const NetworkChatPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const {
    setChatId,
    fetchMessages,
    uploadNetwork,
    createChat
  } = useChatStore();
  const { nodes, links, networkId } = useNetworkStore();
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  
  // Sidebar Logic
  const [showChatList, setShowChatList] = useState(false);

  // Check authentication
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: `/chat/${id}` }});
    }
  }, [isAuthenticated, navigate, id]);

  const creationAttempted = useRef(false);

  // Handle "new" chat creation
  useEffect(() => {
    if (id === 'new' && isAuthenticated && !creationAttempted.current) {
      creationAttempted.current = true;
      const initNewChat = async () => {
        try {
          const newChat = await createChat("New Chat");
          navigate(`/chat/${newChat.id}`, { replace: true });
        } catch (error) {
          console.error("Failed to create new chat:", error);
          navigate('/');
          creationAttempted.current = false;
        }
      };
      initNewChat();
    }
  }, [id, isAuthenticated, createChat, navigate]);

  // Load chat messages and details when component mounts
  useEffect(() => {
    if (id && id !== 'new' && isAuthenticated) {
      const numericId = parseInt(id);
      if (isNaN(numericId)) return;

      setChatId(numericId);

      const loadData = async () => {
        try {
          useNetworkStore.getState().reset();
          await useChatStore.getState().fetchChat(numericId);
          await fetchMessages(numericId);
        } catch (error) {
          console.error("Failed to load chat data:", error);
          if (error.response && error.response.status === 404) {
            navigate('/');
          }
        }
      };
      
      loadData();
    }
  }, [id, fetchMessages, isAuthenticated, navigate, setChatId]);

  // --- Real-time Connection Logic (Refactored) ---
  
  // Define Event Handlers (Memoized to prevent hook re-renders)
  const eventHandlers = useMemo(() => ({
    render_update: (data) => {
      console.log("Render Update:", data);
      useNetworkStore.getState().setNetworkData(data);
      useChatStore.getState().setIsLoading(false);
      useChatStore.getState().setThinkingMessage(null);
    },
    thinking_stream: (data) => {
       const content = data.content || data;
       useChatStore.getState().setThinkingMessage(content);
       useChatStore.getState().setIsLoading(true);
    },
    tool_execution: (data) => {
      console.log("Tool execution:", data);
      if (data.status === 'started') {
        useChatStore.getState().setThinkingMessage(`Executing ${data.tool}...`);
        useChatStore.getState().setIsLoading(true);
      } else if (data.status === 'completed') {
        useChatStore.getState().setThinkingMessage(`${data.tool} completed`);
      } else if (data.status === 'failed') {
        console.error(`Tool ${data.tool} failed:`, data.error);
        useChatStore.getState().setThinkingMessage(null);
        useChatStore.getState().setIsLoading(false);
      }
    },
    message: (data) => {
      useChatStore.getState().addMessage(data);
    },
    message_chunk: (data) => {
      useChatStore.getState().appendMessageChunk(data.content);
    },
    message_complete: (data) => {
       useChatStore.getState().finalizeStreamingMessage(data.id);
    },
    system_message: (data) => {
      console.log("System:", data);
    },
    error: (data) => {
       console.error("Backend reported error:", data);
       useChatStore.getState().setThinkingMessage(null);
       useChatStore.getState().setIsLoading(false);
       // We can choose to show this in the error banner via state update if we want
       // But the hook manages general connection errors. Backend errors are application level.
    }
  }), []);

  // Use the Custom Hook
  const numericId = parseInt(id);
  const shouldConnect = id && id !== 'new' && isAuthenticated && !isNaN(numericId);
  const sseUrl = shouldConnect ? `/api/chat/${numericId}/stream` : null;
  
  const { isConnected, error: sseError } = useNetworkRealtime(sseUrl, {
    eventHandlers,
    onError: (e) => console.log("SSE Connect Error (Hook):", e)
  });


  // --- Node Interaction ---
  const [selectedNode, setSelectedNode] = useState(null);
  const [nodeDetailsPanelOpen, setNodeDetailsPanelOpen] = useState(false);

  const handleNodeClick = async (nodeData) => {
    try {
        setSelectedNode({ id: nodeData.id, label: nodeData.label });
        setNodeDetailsPanelOpen(true);

        const api = await import('../services/api');
        if (!networkId) return;
        
        const response = await api.getNodeDetails(networkId, nodeData.id);
        if (response && response.data) {
             setSelectedNode(prev => ({ ...prev, details: response.data }));
        }
    } catch (e) {
        console.error("Failed to fetch node details:", e);
    }
  };

  const handleCloseNodeDetails = () => {
      setNodeDetailsPanelOpen(false);
      setSelectedNode(null);
  };
  
  const handleBackgroundClick = () => {
      if (selectedNode) {
          handleCloseNodeDetails();
      }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    try {
      await uploadNetwork(id, file);
      console.log("Upload successful");
    } catch (error) {
      console.error("Upload failed:", error);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // --- Resize Logic ---
  const [sidebarWidth, setSidebarWidth] = useState(window.innerWidth / 4);
  const [isResizing, setIsResizing] = useState(false);

  const startResizing = useCallback(() => setIsResizing(true), []);
  const stopResizing = useCallback(() => setIsResizing(false), []);
  
  const resize = useCallback((mouseMoveEvent) => {
      if (isResizing) {
        const newWidth = window.innerWidth - mouseMoveEvent.clientX;
        if (newWidth > 200 && newWidth < window.innerWidth * 0.8) {
          setSidebarWidth(newWidth);
        }
      }
    },[isResizing]);

  useEffect(() => {
    window.addEventListener("mousemove", resize);
    window.addEventListener("mouseup", stopResizing);
    return () => {
      window.removeEventListener("mousemove", resize);
      window.removeEventListener("mouseup", stopResizing);
    };
  }, [resize, stopResizing]);

  const [showLabels, setShowLabels] = useState(false);

  if (!isAuthenticated) return null;

  return (
    <div style={{ display: 'flex', height: '100%', flexDirection: 'column' }}>
      {/* Error notification */}
      {sseError && (
        <div style={{
          padding: '10px',
          backgroundColor: '#f44336',
          color: 'white',
          textAlign: 'center',
          width: '100%'
        }}>
          {sseError}
        </div>
      )}
      
      {/* Main content */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* Left Side: Navigation Sidebar (Collapsible) */}
        {showChatList && (
            <div style={{ 
                width: '250px', 
                borderRight: '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column'
            }}>
                <div style={{ padding: '0.5rem', textAlign: 'right', borderBottom: '1px solid #eee' }}>
                    <button onClick={() => setShowChatList(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem' }}>×</button>
                </div>
                <ChatList currentChatId={parseInt(id)} onClose={() => {}} />
            </div>
        )}

        {/* Center: Graph */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          
           {/* Sidebar Toggle Button (if closed) */}
           {!showChatList && (
            <div style={{ position: 'absolute', top: 10, left: 10, zIndex: 6 }}>
               <button 
                onClick={() => setShowChatList(true)}
                className="btn"
                style={{ 
                    backgroundColor: 'rgba(255, 255, 255, 0.9)', 
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                    padding: '8px 12px',
                    borderRadius: '5px'
                }}
               >
                   ☰ Chats
               </button>
            </div>
           )}

          {/* Graph Controls */}
          {nodes.length > 0 && (
            <div style={{ 
              position: 'absolute', 
              top: 10, 
              left: !showChatList ? 100 : 10, 
              zIndex: 5,
              backgroundColor: 'rgba(255, 255, 255, 0.8)',
              padding: '8px',
              borderRadius: '5px',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}>
              <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', fontSize: '14px' }}>
                <input
                  type="checkbox"
                  checked={showLabels}
                  onChange={(e) => setShowLabels(e.target.checked)}
                  style={{ marginRight: '8px' }}
                />
                Show Labels
              </label>
            </div>
          )}

          {nodeDetailsPanelOpen && selectedNode && (
            <NodeDetailsPanel selectedNode={selectedNode} onClose={handleCloseNodeDetails} />
          )}

          <NetworkGraph 
            nodes={nodes} 
            links={links} 
            showLabels={showLabels} 
            onNodeClick={handleNodeClick}
            onBackgroundClick={handleBackgroundClick}
          />
          {nodes.length === 0 && (
            <div style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              textAlign: 'center'
            }}>
              <h3>No network data</h3>
              <p>Upload a GraphML file to get started</p>
              <input
                type="file"
                accept=".graphml,.xml"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
                ref={fileInputRef}
              />
              <button
                onClick={() => fileInputRef.current.click()}
                disabled={isUploading}
                style={{
                  padding: '10px 20px',
                  fontSize: '16px',
                  cursor: 'pointer',
                  backgroundColor: '#4CAF50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px'
                }}
              >
                {isUploading ? 'Uploading...' : 'Upload GraphML'}
              </button>
            </div>
          )}
        </div>
        
        {/* Resize Handle */}
        <div
          onMouseDown={startResizing}
          style={{
            width: '5px',
            cursor: 'col-resize',
            backgroundColor: isResizing ? 'var(--primary-color)' : 'var(--border-color)',
            transition: 'background-color 0.2s',
            zIndex: 10
          }}
        />

        {/* Right Side: Chat Interface */}
        <div style={{ width: sidebarWidth, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderLeft: '1px solid var(--border-color)' }}>
          <ChatInterface selectedNode={selectedNode} />
        </div>
      </div>
    </div>
  );
};

export default NetworkChatPage;
