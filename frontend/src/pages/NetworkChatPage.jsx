import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';
import { useAuthStore } from '../stores/authStore';
import NetworkGraph from '../components/NetworkGraph';
import ChatInterface from '../components/ChatInterface';
import NodeDetailsPanel from '../components/NodeDetailsPanel';

const NetworkChatPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const {
    setChatId,
    chatId,
    fetchMessages,
    uploadNetwork,
    createChat
  } = useChatStore();
  const { nodes, links } = useNetworkStore();
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [sseError, setSseError] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

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
          creationAttempted.current = false; // Reset on failure to allow retry if needed
        }
      };
      initNewChat();
    }
  }, [id, isAuthenticated, createChat, navigate]);

  // Load chat messages and details when component mounts
  useEffect(() => {
    if (id && id !== 'new' && isAuthenticated) {
      const loadData = async () => {
        try {
          // Reset network store immediately to avoid showing previous graph
          useNetworkStore.getState().reset();

          // Fetch chat details (includes network visualization)
          await useChatStore.getState().fetchChat(parseInt(id));
          // Fetch messages
          await fetchMessages(parseInt(id));
        } catch (error) {
          console.error("Failed to load chat data:", error);
          if (error.response && error.response.status === 404) {
            // Chat not found or not owned by user
            navigate('/');
          }
        }
      };
      
      loadData();
    }
  }, [id, fetchMessages, isAuthenticated, navigate]);
  
  // Initialize SSE connection with error handling
  useEffect(() => {
    if (id && id !== 'new' && isAuthenticated) {
      const numericId = parseInt(id);
      if (isNaN(numericId)) return;

      setChatId(numericId);
      setSseError(null);
      
      // Create SSE connection with error handling
      const eventSource = new EventSource(`/api/chat/${numericId}/stream`, { withCredentials: true });
      
      // Set up event handlers
      eventSource.addEventListener('render_update', (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("Render Update:", data);
          useNetworkStore.getState().setNetworkData(data);
          useChatStore.getState().setIsLoading(false);
          useChatStore.getState().setThinkingMessage(null);
        } catch (e) {
          console.error("Error parsing render_update:", e);
        }
      });

      eventSource.addEventListener('thinking_stream', (event) => {
        try {
          const data = JSON.parse(event.data);
          useChatStore.getState().setThinkingMessage(data.content || data);
          useChatStore.getState().setIsLoading(true);
        } catch(e) {
          useChatStore.getState().setThinkingMessage(event.data);
          useChatStore.getState().setIsLoading(true);
        }
      });

      eventSource.addEventListener('tool_execution', (event) => {
        try {
          const data = JSON.parse(event.data);
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
        } catch (e) {
          console.error("Error parsing tool_execution event:", e);
        }
      });

      eventSource.addEventListener('message', (event) => {
        try {
          const data = JSON.parse(event.data);
          useChatStore.getState().addMessage(data);
        } catch (e) {
          console.error("Error parsing message event:", e);
        }
      });
      
      eventSource.addEventListener('system_message', (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("System:", data);
        } catch (e) {
          console.error("Error parsing system_message:", e);
        }
      });
      
      // Enhanced error handling for SSE with retry logic
      eventSource.onerror = (err) => {
        console.error("SSE Error:", err);
        eventSource.close();

        // Don't show error immediately, try to reconnect
        const retryCount = window.sseRetryCount || 0;
        const maxRetries = 3;
        
        if (retryCount < maxRetries) {
          console.log(`Attempting to reconnect... (${retryCount + 1}/${maxRetries})`);
          window.sseRetryCount = retryCount + 1;
          
          // Exponential backoff
          const timeout = Math.min(1000 * Math.pow(2, retryCount), 10000);
          
          setTimeout(() => {
            if (isAuthenticated) {
              setSseError(null); // Clear previous error if any
              
              if (retryCount > 0) {
                 setSseError("Reconnecting...");
              }
              
              setRetryTrigger(prev => prev + 1);
            }
          }, timeout);
        } else {
          window.sseRetryCount = 0; // Reset for next time
          setSseError("Connection lost. Please refresh the page or try logging in again.");
        }
      };
      
      return () => {
        eventSource.close();
      };
    }
  }, [id, setChatId, isAuthenticated, retryTrigger]);

  const [selectedNode, setSelectedNode] = useState(null);
  const [nodeDetailsPanelOpen, setNodeDetailsPanelOpen] = useState(false);

  // Function to handle node clicks from the graph
  const handleNodeClick = async (nodeData) => {
    try {
        // Optimistically set selected node with basic info
        setSelectedNode({ id: nodeData.id, label: nodeData.label });
        setNodeDetailsPanelOpen(true);

        // Dynamically import API to avoid potential circular dependencies if any, 
        // though standard import would work too. Using dynamic for consistency with previous thought process.
        const api = await import('../services/api');
        const response = await api.getNodeDetails(chatId, nodeData.id);
        
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
   
  const handleAskAI = (node) => {
      // Just ensure the panel stays open or whatever logic we need.
      // The context passing happens via props to ChatInterface
      console.log("Asking AI about:", node);
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    try {
      await uploadNetwork(id, file);
      // Success handling if needed, but SSE will trigger updates
      console.log("Upload successful");
    } catch (error) {
      console.error("Upload failed:", error);
      
      // Check if it's an authentication error
      if (error.response && error.response.status === 401) {
        setSseError("Authentication required. Please log in again.");
        // The axios interceptor will handle the redirect
      } else {
        setSseError("Failed to upload file. Please try again.");
      }
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Resizing logic
  const [sidebarWidth, setSidebarWidth] = useState(window.innerWidth / 4);
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef(null);

  const startResizing = React.useCallback((mouseDownEvent) => {
    setIsResizing(true);
  }, []);

  const stopResizing = React.useCallback(() => {
    setIsResizing(false);
  }, []);

  const resize = React.useCallback(
    (mouseMoveEvent) => {
      if (isResizing) {
        const newWidth = window.innerWidth - mouseMoveEvent.clientX;
        if (newWidth > 200 && newWidth < window.innerWidth * 0.8) {
          setSidebarWidth(newWidth);
        }
      }
    },
    [isResizing]
  );

  useEffect(() => {
    window.addEventListener("mousemove", resize);
    window.addEventListener("mouseup", stopResizing);
    return () => {
      window.removeEventListener("mousemove", resize);
      window.removeEventListener("mouseup", stopResizing);
    };
  }, [resize, stopResizing]);

  const [showLabels, setShowLabels] = useState(false);

  // Don't render anything if not authenticated
  if (!isAuthenticated) {
    return null;  // Redirecting to login via useEffect
  }

  return (
    <div style={{ display: 'flex', height: '100vh', flexDirection: 'column' }}>
      {/* Error notification bar */}
      {sseError && (
        <div style={{
          padding: '10px',
          backgroundColor: '#f44336',
          color: 'white',
          textAlign: 'center',
          width: '100%',
          position: 'relative'
        }}>
          {sseError}
          <button
            style={{
              position: 'absolute',
              right: '10px',
              background: 'transparent',
              border: 'none',
              color: 'white',
              cursor: 'pointer'
            }}
            onClick={() => setSseError(null)}
          >
            ×
          </button>
        </div>
      )}
      
      {/* Main content */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {/* Graph Controls */}
          {nodes.length > 0 && (
            <div style={{ 
              position: 'absolute', 
              top: 10, 
              left: 10, 
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
            <NodeDetailsPanel 
              selectedNode={selectedNode} 
              onClose={handleCloseNodeDetails} 
              onAskAI={handleAskAI}
            />
          )}

          <NetworkGraph 
            nodes={nodes} 
            links={links} 
            showLabels={showLabels} 
            onNodeClick={handleNodeClick}
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

        <div style={{ width: sidebarWidth, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderLeft: '1px solid var(--border-color)' }}>
          <ChatInterface selectedNode={selectedNode} />
        </div>
      </div>
    </div>
  );
};

export default NetworkChatPage;
