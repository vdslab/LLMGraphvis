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
            console.log("RX thinking_stream:", data);
            const content = data.content || data;
            if (content) {
                useChatStore.getState().appendThinkingMessage(content);
            }
            useChatStore.getState().setIsLoading(true);
        },
        tool_execution: (data) => {
            console.log("Tool execution:", data);
            if (data.status === 'started') {
                useChatStore.getState().setRunningTool({ name: data.tool, status: 'running' });
                useChatStore.getState().setIsLoading(true);
            } else if (data.status === 'completed') {
                useChatStore.getState().setRunningTool(null);
                
                // Add to the streaming message logs so the marker can find it
                // We construct a partial object since we don't have full args/result here yet in this event
                // But the marker just needs existence usually, or we show what we have.
                // Actually the "started" event had args. We might have missed capturing them for this log.
                // For now, let's just log the name and status.
                useChatStore.getState().addToolExecutionToStreamingMessage({
                    tool_name: data.tool,
                    status: 'completed',
                    // arguments? context? We don't have them in 'completed' event from backend currently.
                    // But for the UI "View details" it might be enough to show "Completed".
                });

            } else if (data.status === 'failed') {
                console.error(`Tool ${data.tool} failed:`, data.error);
                useChatStore.getState().setRunningTool(null);
                useChatStore.getState().setIsLoading(false);
                
                useChatStore.getState().addToolExecutionToStreamingMessage({
                    tool_name: data.tool,
                    status: 'failed',
                    error: data.error
                });
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
            // Turn is fully done: fold the final currentTurnUsage into the lifetime chatUsage total.
            useChatStore.getState().commitTurnUsage();
        },
        // usage_update: { input_tokens, output_tokens, cached_input_tokens, estimated_cost_usd, provider, model }
        // Fired potentially multiple times per turn (once per ReAct-loop iteration), each carrying
        // the running total for the turn so far. commitTurnUsage() (above) folds it into the lifetime
        // total once the turn is fully complete.
        usage_update: (data) => {
            useChatStore.getState().setCurrentTurnUsage(data);
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
