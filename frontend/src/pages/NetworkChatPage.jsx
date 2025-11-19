import React, { useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';
import NetworkGraph from '../components/NetworkGraph';
import ChatInterface from '../components/ChatInterface';

const NetworkChatPage = () => {
  const { id } = useParams();
  const { setChatId, chatId } = useChatStore();
  const { nodes, links } = useNetworkStore();
  
  useEffect(() => {
    if (id) {
      setChatId(parseInt(id));
      // Initialize SSE connection here or in store
      // For now, let's assume store handles it or we do it here
      const eventSource = new EventSource(`/api/chat/${id}/stream`);
      
      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // Handle events (render_update, message, etc.)
        // This logic should ideally be in the store or a hook
        console.log("SSE Event:", data);
      };
      
      return () => {
        eventSource.close();
      };
    }
  }, [id, setChatId]);

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <div style={{ flex: 1, borderRight: '1px solid var(--border-color)', position: 'relative' }}>
        <NetworkGraph nodes={nodes} links={links} />
      </div>
      <div style={{ width: '400px', display: 'flex', flexDirection: 'column' }}>
        <ChatInterface />
      </div>
    </div>
  );
};

export default NetworkChatPage;
