import { create } from "zustand";
import { networkChatAPI } from "./api";
import useNetworkStore from "./networkStore";

const useChatStore = create((set, get) => ({
  messages: [],
  isProcessing: false,
  error: null,
  currentConversationId: null,

  setCurrentConversationId: (conversationId) => {
    set({ currentConversationId: conversationId, messages: [] }); // Clear messages when changing conversation
  },

  // Add a message to the chat history
  addMessage: (message) => {
    set((state) => ({
      messages: [
        ...state.messages,
        { ...message, timestamp: new Date().toISOString() },
      ],
    }));
  },

  // Send a message to the backend and handle the response
  sendMessage: async (messageContent) => {
    if (!messageContent.trim()) return;

    const { addMessage, currentConversationId } = get();

    // Add user message immediately to the UI
    addMessage({ role: "user", content: messageContent });
    set({ isProcessing: true, error: null });

    try {
      // Call the backend API
      const response = await networkChatAPI.processChatMessage({
        message: messageContent,
        conversation_id: currentConversationId,
      });

      const result = response.data;

      if (result && result.success) {
        // Add the assistant's response to the UI
        addMessage({ role: "assistant", content: result.content });

        // Handle any network updates returned from the backend
        if (result.networkUpdate) {
          console.log("Received network update:", result.networkUpdate);
          const { type, ...updateData } = result.networkUpdate;
          const networkStore = useNetworkStore.getState();

          if (type === "calculate_and_store_centrality") {
            // Handle two-stage centrality result
            const {
              stage1,
              stage2,
              visualization_data,
              centrality_type,
              calculation_id,
            } = updateData;

            if (stage2 && visualization_data) {
              // Both stages completed successfully
              console.log(
                "Two-stage centrality processing completed successfully",
              );

              // Apply visualization data to network
              networkStore.applyCentralityVisualizationData(
                visualization_data,
                centrality_type,
                calculation_id,
              );

              // Add success message
              addMessage({
                role: "assistant",
                content: `✅ ${centrality_type.charAt(0).toUpperCase() + centrality_type.slice(1)} centrality visualization completed successfully! The network now shows nodes sized and colored by their centrality values.`,
                metadata: { centrality_type, calculation_id },
              });
            } else if (stage1 && !stage2) {
              // Only stage 1 completed
              console.log("Stage 1 completed, stage 2 failed");
              addMessage({
                role: "assistant",
                content: `⚠️ ${centrality_type.charAt(0).toUpperCase() + centrality_type.slice(1)} centrality calculation completed, but visualization failed. The centrality values were calculated and stored with ID: ${calculation_id}`,
                metadata: {
                  centrality_type,
                  calculation_id,
                  partial_success: true,
                },
              });
            }
          } else if (
            type === "calculate_centrality" &&
            updateData.centrality_values
          ) {
            // Legacy single-stage centrality
            networkStore.applyCentralityValues(
              updateData.centrality_values,
              updateData.centrality_type,
            );
          } else if (type === "change_layout" && updateData.positions) {
            // Update node positions based on new layout
            const { positions: newPositionsData } = updateData;
            const currentPositions = networkStore.positions;

            const newPositions = currentPositions.map((node) => {
              const newPos = newPositionsData[node.id];
              if (newPos) {
                return { ...node, x: newPos.x, y: newPos.y };
              }
              return node;
            });

            networkStore.setPositions(newPositions);
          }
        }

        // Update the current conversation ID if it's a new conversation
        if (result.conversation_id && !currentConversationId) {
          set({ currentConversationId: result.conversation_id });
        }
      } else {
        // Handle backend error response
        const errorMessage = result.content || "An unknown error occurred.";
        addMessage({
          role: "assistant",
          content: `Error: ${errorMessage}`,
          error: true,
        });
        set({ error: errorMessage });
      }
    } catch (error) {
      console.error("Error sending message:", error);
      const errorMessage =
        error.response?.data?.content ||
        error.message ||
        "Failed to connect to the server.";
      addMessage({
        role: "assistant",
        content: `Error: ${errorMessage}`,
        error: true,
      });
      set({ error: errorMessage });
    } finally {
      set({ isProcessing: false });
    }
  },

  // Clear all messages and reset conversation
  clearChat: () => {
    set({ messages: [], error: null, currentConversationId: null });
  },
}));

export default useChatStore;
