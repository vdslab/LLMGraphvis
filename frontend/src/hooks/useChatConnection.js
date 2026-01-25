import { useMemo } from 'react';
import { useNetworkRealtime } from './useNetworkRealtime';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

export const useChatConnection = (id, isAuthenticated) => {
    // Define Event Handlers (Memoized to prevent hook re-renders)
    const eventHandlers = useMemo(() => ({
        render_update: (data) => {
            console.log("Render Update:", data);
            useNetworkStore.getState().setNetworkData(data);
            
            // Fix for lost network ID context: Sync ID if backend provides it
            if (data.network_id) {
                useNetworkStore.getState().setNetworkId(data.network_id);
            }

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
            useChatStore.getState().finalizeStreamingMessage(data.id, data.content, data.tool_executions);
        },
        system_message: (data) => {
            console.log("System:", data);
        },
        error: (data) => {
            console.error("Backend reported error:", data);
            useChatStore.getState().setThinkingMessage(null);
            useChatStore.getState().setIsLoading(false);
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

    return { isConnected, sseError };
};
