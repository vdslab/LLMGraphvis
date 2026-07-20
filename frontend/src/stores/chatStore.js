import { create } from 'zustand';
import { useNetworkStore } from './networkStore';
import {
  getChats,
  getChat,
  getChatMessages,
  exportNetwork,
  createChat as createChatAPI,
  updateChat as updateChatAPI,
  processMessage as processMessageAPI,
  uploadGraphML,
  getLlmProviders
} from '../services/api';

export const useChatStore = create((set, get) => ({
  chatId: null,
  messages: [],
  isLoading: false,
  thinkingMessage: null,
  streamingMessageId: null,
  runningTool: null,

  // Per-chat LLM provider/model pin (null means "use server default")
  chatProvider: null,
  chatModel: null,
  llmProviders: [],

  // Token/cost usage tracking (Stage 7)
  chatUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0 },   // lifetime total for this chat session (client-side accumulation across turns)
  currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0, provider: null, model: null },  // running total for the turn currently in progress

  // Get all chats for current user
  fetchChats: async () => {
    const res = await getChats();
    return res.data;
  },
  
  // Get chat details
  fetchChat: async (chatId) => {
    const res = await getChat(chatId);
    
    // Race condition guard: ensure we are still on the requested chat
    if (get().chatId !== chatId) return;

    if (res.data.network) {
      useNetworkStore.getState().setNetworkData(res.data.network);
    } else {
      useNetworkStore.getState().reset();
    }
    
    // Sync network ID if present
    if (res.data.network_id) {
       useNetworkStore.getState().setNetworkId(res.data.network_id);
    }

    set({ chatProvider: res.data.provider ?? null, chatModel: res.data.model ?? null });

    return res.data;
  },

  // Load the catalog of provider/model options a chat can be pinned to
  fetchLlmProviders: async () => {
    if (get().llmProviders.length > 0) return get().llmProviders;
    const res = await getLlmProviders();
    set({ llmProviders: res.data });
    return res.data;
  },

  // Pin (or clear, with null) this chat's provider/model
  updateChatSettings: async (chatId, { provider, model }) => {
    const res = await updateChatAPI(chatId, { provider, model });
    set({ chatProvider: res.data.provider ?? null, chatModel: res.data.model ?? null });
    return res.data;
  },
  
  // Get message history
  fetchMessages: async (chatId = null) => {
    const id = chatId || get().chatId;
    if (!id) return;
    
    const res = await getChatMessages(id);
    
    // Race condition guard
    if (get().chatId !== id) return;

    let inputTokens = 0;
    let outputTokens = 0;
    let estimatedCostUsd = 0;

    res.data.forEach(msg => {
      if (msg.usage) {
        inputTokens += msg.usage.input_tokens || 0;
        outputTokens += msg.usage.output_tokens || 0;
        estimatedCostUsd += msg.usage.estimated_cost_usd || 0;
      }
    });

    set({ 
      messages: res.data,
      chatUsage: { inputTokens, outputTokens, estimatedCostUsd },
      currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0, provider: null, model: null }
    });
    return res.data;
  },

  // Create a new chat
  createChat: async (name) => {
    const res = await createChatAPI(name);
    set({ chatId: res.data.id, messages: [] });
    useNetworkStore.getState().setNetworkId(res.data.network_id);
    return res.data;
  },

  // Rename a chat
  renameChat: async (chatId, name) => {
    const res = await import('../services/api').then(module => module.updateChat(chatId, { name }));
    // We don't strictly manage the chats list in store but since ChatList calls fetchChats on mount, and we might want to update it.
    // Ideally we should just return success and let component handle or update list if we had one.
    // Let's just return data. The component can optimistically update or refetch.
    return res.data;
  },

  // Upload network file to chat
  uploadNetwork: async (chatId, file) => {
    set({ isLoading: true, thinkingMessage: "" });
    try {
      await uploadGraphML(chatId, file);
      // Response is 202 Accepted.
      // SSE will handle the rest.
    } catch (error) {
      console.error("Failed to upload network:", error);
      set({ isLoading: false, thinkingMessage: null });
      throw error;
    }
  },

  // Send message to process
  sendMessage: async (content) => {
    const { chatId, messages } = get();
    // Optimistic update - add user message immediately
    const newMessage = { role: 'user', content, id: Date.now(), created_at: new Date().toISOString() };
    set({ messages: [...messages, newMessage], isLoading: true, thinkingMessage: "" });

    try {
      await processMessageAPI(chatId, content);
      // Response is 202 Accepted.
      // SSE will handle the rest.
    } catch (error) {
      console.error("Failed to send message:", error);
      set({ isLoading: false, thinkingMessage: null });
      throw error;
    }
  },
  
  // Export network as GraphML
  exportNetworkAsGraphML: async (chatId = null) => {
    const id = chatId || get().chatId;
    if (!id) return;
    
    const response = await exportNetwork(id);
    
    // Create a download link
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `network_${id}.graphml`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },

  addMessage: (message) => {
    set((state) => {
      // Deduplicate: Check if message with same ID already exists
      if (state.messages.some(m => m.id === message.id)) {
        return { isLoading: false, thinkingMessage: null };
      }
      
      // Also check if we have a streaming message that needs to be replaced/merged
      // This handles the race condition where `message` event arrives but we have a `isStreaming` placeholder
      
      // Use ID check if available, otherwise strict role/streaming check
      const streamingMsg = state.streamingMessageId 
        ? state.messages.find(m => m.id === state.streamingMessageId)
        : state.messages.find(m => m.isStreaming && m.role === 'assistant');

      if (streamingMsg && message.role === 'assistant') {
         // Assuming this is the finalized version of the streaming message
         const updatedMessages = state.messages.map(m => {
            if (m.id === streamingMsg.id) {
                return { ...message, isStreaming: false };
            }
            return m;
         });
         return { 
            messages: updatedMessages, 
            isLoading: false, 
            thinkingMessage: null,
            streamingMessageId: null 
         };
      }

      return { 
        messages: [...state.messages, message],
        isLoading: false,
        thinkingMessage: null
      };
    });
  },

  appendMessageChunk: (content) => {
    set((state) => {
      const messages = [...state.messages];
      let msgIndex = -1;
      
      // 1. Try to find by streamingMessageId
      if (state.streamingMessageId) {
          msgIndex = messages.findIndex(m => m.id === state.streamingMessageId);
      }
      
      // 2. Fallback: Find last streaming assistant message
      if (msgIndex === -1) {
          msgIndex = messages.findLastIndex(m => m.isStreaming && m.role === 'assistant');
      }

      if (msgIndex !== -1) {
        // Update existing
        const msg = { ...messages[msgIndex] };
        msg.content += content;
        messages[msgIndex] = msg;
        return { 
          messages,
          thinkingMessage: null 
        };
      } else {
        // Create new
        const newId = Date.now();
        const newMessage = {
          role: 'assistant',
          content,
          id: newId,
          created_at: new Date().toISOString(),
          isStreaming: true,
          tool_executions: []
        };
        return { 
          messages: [...messages, newMessage],
          thinkingMessage: null,
          streamingMessageId: newId
        };
      }
    });
  },

  addToolExecutionToStreamingMessage: (toolData) => {
      set((state) => {
          if (!state.streamingMessageId) return {};

          const messages = [...state.messages];
          const idx = messages.findIndex(m => m.id === state.streamingMessageId);
          if (idx === -1) return {};

          const msg = { ...messages[idx] };
          if (!msg.tool_executions) msg.tool_executions = [];
          
          msg.tool_executions = [...msg.tool_executions, toolData];
          messages[idx] = msg;
          
          return { messages };
      });
  },

  finalizeStreamingMessage: (realId, content = null, tool_executions = null) => {
    set((state) => {
      const messages = [...state.messages];
      // Use findLast or specific ID
      const idx = state.streamingMessageId 
        ? messages.findIndex(m => m.id === state.streamingMessageId)
        : messages.findLastIndex(m => m.isStreaming);
        
      if (idx !== -1) {
        messages[idx].isStreaming = false;
        if (realId) {
            messages[idx].id = realId;
        }
        if (content) {
            messages[idx].content = content;
        }
        if (tool_executions) {
            messages[idx].tool_executions = tool_executions;
        }
      }
      return { messages, isLoading: false, thinkingMessage: null, streamingMessageId: null };
    });
  },

  setThinkingMessage: (msg) => set({ thinkingMessage: msg }),
  setRunningTool: (tool) => set({ runningTool: tool }),

  appendThinkingMessage: (chunk) => set((state) => ({
    thinkingMessage: (state.thinkingMessage || "") + chunk
  })),

  setIsLoading: (loading) => set({ isLoading: loading }),

  setChatId: (id) => set({ chatId: id }),

  // Usage tracking (Stage 7): usage_update SSE events carry a RUNNING TOTAL for the
  // in-progress turn (not deltas), so this replaces currentTurnUsage wholesale each time.
  setCurrentTurnUsage: (data) => set({
    currentTurnUsage: {
      inputTokens: data.input_tokens ?? 0,
      outputTokens: data.output_tokens ?? 0,
      estimatedCostUsd: data.estimated_cost_usd ?? 0,
      provider: data.provider ?? null,
      model: data.model ?? null,
    }
  }),

  // Folds the now-final currentTurnUsage into the lifetime chatUsage total, then
  // resets currentTurnUsage for the next turn. Call this once, when a turn fully completes.
  commitTurnUsage: () => set((state) => ({
    chatUsage: {
      inputTokens: state.chatUsage.inputTokens + state.currentTurnUsage.inputTokens,
      outputTokens: state.chatUsage.outputTokens + state.currentTurnUsage.outputTokens,
      estimatedCostUsd: state.chatUsage.estimatedCostUsd + state.currentTurnUsage.estimatedCostUsd,
    },
    currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0, provider: null, model: null },
  })),

  // Note: no existing reset()/clearChat()-style action was found in this store to hook into
  // (chat switches go through setChatId + fetchChat + fetchMessages, none of which "reset" state).
  // This action is provided for future wiring but is not currently called anywhere.
  resetUsage: () => set({
    chatUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0 },
    currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0, provider: null, model: null }
  })
}));
