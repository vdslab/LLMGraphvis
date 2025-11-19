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
        // console.log("Raw SSE:", event.data);
        // SSE format usually sends "data: ..." but EventSource handles that.
        // However, our backend implementation might be sending raw JSON or specific event fields.
        // Let's check the event type if using named events, or parse data.
        
        try {
            const parsed = JSON.parse(event.data);
            // If our backend sends {event: "name", data: ...} inside the data field (which is double encoding if using standard SSE)
            // Standard SSE: 
            // event: render_update
            // data: {...}
            
            // My backend implementation in llm_service.py:
            // yield {"event": event_name, "data": data_content}
            // sse_starlette handles formatting this into standard SSE.
            
            // So on client side:
            // eventSource.addEventListener('render_update', (e) => ...)
            // But here we are using onmessage which catches 'message' events or all?
            // Actually onmessage only catches events without a type or type='message'.
            // We need addEventListener for custom types.
        } catch (e) {
             console.error("SSE Parse Error", e);
        }
      };

      eventSource.addEventListener('render_update', (event) => {
          const data = JSON.parse(event.data);
          console.log("Render Update:", data);
          useNetworkStore.getState().setNetworkData(data);
          useChatStore.getState().setIsLoading(false);
          useChatStore.getState().setThinkingMessage(null);
      });

      eventSource.addEventListener('thinking_stream', (event) => {
          // data might be a string or JSON
          try {
            const data = JSON.parse(event.data);
            useChatStore.getState().setThinkingMessage(data.content || data);
          } catch(e) {
             useChatStore.getState().setThinkingMessage(event.data);
          }
      });

      eventSource.addEventListener('message', (event) => {
          const data = JSON.parse(event.data);
          useChatStore.getState().addMessage(data);
      });
      
      eventSource.addEventListener('system_message', (event) => {
          const data = JSON.parse(event.data);
          // Maybe add as a system message to chat?
          // For now just log or alert
          console.log("System:", data);
      });
      
      eventSource.onerror = (err) => {
          console.error("SSE Error:", err);
          eventSource.close();
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
