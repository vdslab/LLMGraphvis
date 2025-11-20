import axios from 'axios';
import { useAuthStore } from '../stores/authStore';

const api = axios.create({
  baseURL: '/api', // Proxy handles the rest
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important for HttpOnly cookies
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Ignore 401 from checkAuth to allow non-logged in users to visit /register
      if (error.config.url && error.config.url.includes('/auth/users/me')) {
        return Promise.reject(error);
      }

      // Redirect to login or clear auth state
      // We can't use hooks here directly, but we can access the store
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Get all chats
export const getChats = () => api.get('/chat');

// Get specific chat
export const getChat = (chatId) => api.get(`/chat/${chatId}`);

// Get chat messages
export const getChatMessages = (chatId) => api.get(`/chat/${chatId}/messages`);

// Export network
export const exportNetwork = (chatId) =>
  api.get(`/chat/${chatId}/export`, { responseType: 'blob' });

// Create chat
export const createChat = (name) => api.post('/chat', { name });

// Process message
export const processMessage = (chatId, content) =>
  api.post(`/chat/${chatId}/process`, {
    message: { content }
  });

export const uploadGraphML = async (chatId, file) => {
  const formData = new FormData();
  formData.append('file', file);

  return api.post(`/chat/${chatId}/upload`, formData);
};

export default api;
