import { create } from 'zustand';
import { useNetworkStore } from './networkStore';
import {
  getChats,
  getChat,
  getChatMessages,
  exportNetwork,
  createChat as createChatAPI,
  processMessage as processMessageAPI,
  uploadGraphML
} from '../services/api';

export const useChatStore = create((set, get) => ({
  chatId: null,
  messages: [],
  isLoading: false,
  thinkingMessage: null,
  streamingMessageId: null,

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

    return res.data;
  },
  
  // Get message history
  fetchMessages: async (chatId = null) => {
    const id = chatId || get().chatId;
    if (!id) return;
    
    const res = await getChatMessages(id);
    
    // Race condition guard
    if (get().chatId !== id) return;

    set({ messages: res.data });
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
    set({ isLoading: true, thinkingMessage: "Uploading..." });
    await uploadGraphML(chatId, file);
    // Response is 202 Accepted.
    // SSE will handle the rest.
  },

  // Send message to process
  sendMessage: async (content) => {
    const { chatId, messages } = get();
    // Optimistic update - add user message immediately
    const newMessage = { role: 'user', content, id: Date.now(), created_at: new Date().toISOString() };
    set({ messages: [...messages, newMessage], isLoading: true, thinkingMessage: "Processing..." });

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
          isStreaming: true
        };
        return { 
          messages: [...messages, newMessage],
          thinkingMessage: null,
          streamingMessageId: newId
        };
      }
    });
  },

  finalizeStreamingMessage: (realId) => {
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
      }
      return { messages, isLoading: false, thinkingMessage: null, streamingMessageId: null };
    });
  },

  setThinkingMessage: (msg) => set({ thinkingMessage: msg }),
  
  setIsLoading: (loading) => set({ isLoading: loading }),
  
  setChatId: (id) => set({ chatId: id })
}));
