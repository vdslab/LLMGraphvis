import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';
import { useAuthStore } from '../stores/authStore';
import NetworkGraph from '../components/NetworkGraph';
import ChatInterface from '../components/ChatInterface';

const NetworkChatPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const {
    setChatId,
    chatId,
    fetchMessages,
    uploadNetwork
  } = useChatStore();
  const { nodes, links } = useNetworkStore();
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [sseError, setSseError] = useState(null);

  // Check authentication
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: `/chat/${id}` }});
    }
  }, [isAuthenticated, navigate, id]);

  // Load chat messages when component mounts
  useEffect(() => {
    if (id && isAuthenticated) {
      const loadMessages = async () => {
        try {
          await fetchMessages(parseInt(id));
        } catch (error) {
          console.error("Failed to load messages:", error);
          if (error.response && error.response.status === 404) {
            // Chat not found or not owned by user
            navigate('/');
          }
        }
      };
      
      loadMessages();
    }
  }, [id, fetchMessages, isAuthenticated, navigate]);
  
  // Initialize SSE connection with error handling
  useEffect(() => {
    if (id && isAuthenticated) {
      setChatId(parseInt(id));
      setSseError(null);
      
      // Create SSE connection with error handling
      const eventSource = new EventSource(`/api/chat/${id}/stream`);
      
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
      
      // Enhanced error handling for SSE
      eventSource.onerror = (err) => {
        console.error("SSE Error:", err);
        
        // Check if the connection was closed due to authentication error
        if (eventSource.readyState === EventSource.CLOSED) {
          setSseError("Connection lost. You may need to log in again.");
          
          // Try to reconnect once after a short delay
          setTimeout(() => {
            if (isAuthenticated) {
              // If still authenticated according to local state, try reconnecting
              const newEventSource = new EventSource(`/api/chat/${id}/stream`);
              
              // If it immediately fails again, redirect to login
              newEventSource.onerror = () => {
                newEventSource.close();
                // The axios interceptor will handle 401 redirect
              };
            }
          }, 2000);
        }
        
        eventSource.close();
      };
      
      return () => {
        eventSource.close();
      };
    }
  }, [id, setChatId, isAuthenticated]);

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
      <div style={{ display: 'flex', flex: 1 }}>
        <div style={{ flex: 1, borderRight: '1px solid var(--border-color)', position: 'relative' }}>
          <NetworkGraph nodes={nodes} links={links} />
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
        <div style={{ width: '400px', display: 'flex', flexDirection: 'column' }}>
          <ChatInterface />
        </div>
      </div>
    </div>
  );
};

export default NetworkChatPage;
