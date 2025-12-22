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

  // Get all chats for current user
  fetchChats: async () => {
    const res = await getChats();
    return res.data;
  },
  
  // Get chat details
  fetchChat: async (chatId) => {
    const res = await getChat(chatId);
    if (res.data.network) {
      useNetworkStore.getState().setNetworkData(res.data.network);
    } else {
      useNetworkStore.getState().reset();
    }
    return res.data;
  },
  
  // Get message history
  fetchMessages: async (chatId = null) => {
    const id = chatId || get().chatId;
    if (!id) return;
    
    const res = await getChatMessages(id);
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

  // Upload network file to chat
  uploadNetwork: async (chatId, file) => {
    set({ isLoading: true, thinkingMessage: "Uploading and initializing network..." });
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
      const streamingMsg = state.messages.find(m => m.isStreaming && m.role === 'assistant');
      if (streamingMsg && message.role === 'assistant') {
         // Assuming this is the finalized version of the streaming message
         // We Map it properly
         const updatedMessages = state.messages.map(m => {
            if (m.isStreaming && m.role === 'assistant') {
                return { ...message, isStreaming: false };
            }
            return m;
         });
         return { messages: updatedMessages, isLoading: false, thinkingMessage: null };
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
      const lastMessage = messages[messages.length - 1];

      if (lastMessage && lastMessage.role === 'assistant' && lastMessage.isStreaming) {
        // Append to existing streaming message
        lastMessage.content += content;
        return { 
          messages,
          // Hide thinking message as soon as we have content
          thinkingMessage: null 
        };
      } else {
        // Create new streaming message
        const newMessage = {
          role: 'assistant',
          content,
          id: Date.now(), // Temporary ID until confirmed
          created_at: new Date().toISOString(),
          isStreaming: true
        };
        return { 
          messages: [...messages, newMessage],
          thinkingMessage: null
        };
      }
    });
  },

  finalizeStreamingMessage: (realId) => {
    set((state) => {
      const messages = [...state.messages];
      const lastMessage = messages[messages.length - 1];
      if (lastMessage && lastMessage.isStreaming) {
        lastMessage.isStreaming = false;
        if (realId) {
            lastMessage.id = realId;
        }
      }
      return { messages, isLoading: false, thinkingMessage: null };
    });
  },

  setThinkingMessage: (msg) => set({ thinkingMessage: msg }),
  
  setIsLoading: (loading) => set({ isLoading: loading }),
  
  setChatId: (id) => set({ chatId: id })
}));
