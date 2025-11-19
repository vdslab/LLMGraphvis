import { create } from 'zustand';
import api from '../services/api';
import { useNetworkStore } from './networkStore';

export const useChatStore = create((set, get) => ({
  chatId: null,
  messages: [],
  isLoading: false,
  thinkingMessage: null,

  createChat: async (name) => {
    const res = await api.post('/chat', { name });
    set({ chatId: res.data.id, messages: [] });
    useNetworkStore.getState().setNetworkId(res.data.network_id);
    return res.data;
  },

  uploadNetwork: async (chatId, file) => {
    const formData = new FormData();
    formData.append('file', file); // Backend expects raw body or file? Spec says "GraphML data".
    // Wait, spec says POST /chat/{id}/upload (GraphML data).
    // Usually this means file upload.
    // Let's assume backend handles file upload or raw body.
    // My backend implementation for upload is not yet detailed in routers/chat.py, 
    // but standard is multipart/form-data or raw bytes.
    // I'll implement as multipart for file upload.
    
    // Note: I haven't implemented the upload endpoint in backend yet!
    // I need to add that to backend/routers/chat.py later.
    
    set({ isLoading: true, thinkingMessage: "Uploading and initializing network..." });
    await api.post(`/chat/${chatId}/upload`, formData);
    // Response is 202 Accepted.
    // SSE will handle the rest.
  },

  sendMessage: async (content) => {
    const { chatId, messages } = get();
    // Optimistic update
    const newMessage = { role: 'user', content, id: Date.now() };
    set({ messages: [...messages, newMessage], isLoading: true, thinkingMessage: "Waiting for response..." });

    await api.post(`/chat/${chatId}/process`, { message: { role: 'user', content } });
    // Response is 202 Accepted.
    // SSE will handle the rest.
  },

  addMessage: (message) => {
    set((state) => ({ 
      messages: [...state.messages, message],
      isLoading: false,
      thinkingMessage: null
    }));
  },

  setThinkingMessage: (msg) => set({ thinkingMessage: msg }),
  
  setIsLoading: (loading) => set({ isLoading: loading }),
  
  setChatId: (id) => set({ chatId: id })
}));
