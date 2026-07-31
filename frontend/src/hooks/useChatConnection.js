import { useMemo } from 'react';
import { useNetworkRealtime } from './useNetworkRealtime';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

export const useChatConnection = (id, isAuthenticated) => {
    // Define Event Handlers (Memoized to prevent hook re-renders)
    const eventHandlers = useMemo(() => ({
        render_update: (data) => {
            useNetworkStore.getState().setNetworkData(data);

            // Fix for lost network ID context: Sync ID if backend provides it
            if (data.network_id) {
                useNetworkStore.getState().setNetworkId(data.network_id);
            }
            // Deliberately does NOT end the turn. A visualization tool renders
            // mid-turn and the agent keeps working afterwards; treating this as
            // terminal made the status indicator flicker off and back on.
        },
        // Backend pipeline steps ("Importing GraphML data"). These are our own
        // labels — thinking_stream below is the model's reasoning, and mixing
        // the two is what made non-thinking show up under "Thinking".
        progress: (data) => {
            useChatStore.getState().setProgress({
                label: data.label,
                status: data.status || 'running',
            });
        },
        thinking_stream: (data) => {
            const content = data.content || data;
            if (content) {
                useChatStore.getState().appendThinkingMessage(content);
            }
            useChatStore.getState().setIsLoading(true);
        },
        tool_execution: (data) => {
            if (data.status === 'started') {
                useChatStore.getState().setRunningTool({ name: data.tool, status: 'running' });
                useChatStore.getState().setIsLoading(true);
                // Clear the live thought preview so the next generation's thinking_stream
                // chunks don't run on directly after this iteration's leftover text.
                useChatStore.getState().setThinkingMessage(null);
            } else if (data.status === 'completed') {
                useChatStore.getState().setRunningTool(null);

                // Placeholder for the inline marker already in the transcript.
                // The full record (arguments, timings) arrives with
                // message_complete and replaces this.
                useChatStore.getState().addToolExecutionToStreamingMessage({
                    tool_name: data.tool,
                    status: 'completed',
                });
            } else if (data.status === 'failed') {
                console.error(`Tool ${data.tool} failed:`, data.error);
                useChatStore.getState().setRunningTool(null);

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
        // The backend named the chat for us (from the uploaded filename, or from
        // the first exchange). Never fires for a chat the user renamed by hand.
        chat_renamed: (data) => {
            if (data && data.name) {
                useChatStore.getState().setChatName(data.name);
            }
        },
        system_message: (data) => {
            console.log("System:", data);
        },
        error: (data) => {
            console.error("Backend reported error:", data);
            useChatStore.getState().endTurn();
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
