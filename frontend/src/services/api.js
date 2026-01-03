import axios from 'axios';
// import { useAuthStore } from '../stores/authStore';

const api = axios.create({
  baseURL: '/api', // Proxy handles the rest
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important for HttpOnly cookies
  timeout: 60000, // 60 seconds timeout
});

// Retry configuration
const RETRY_COUNT = 3;
const RETRY_DELAY = 1000; // 1 second

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;

    // If config does not exist or the retry option is not set, reject
    if (!config || !config.retry) {
        // Set default retry count if not present
        if (config && !config.retryCount) {
            config.retryCount = 0;
        }
    }

    // Check if we should retry
    // Retry on network errors or 5xx server errors
    // Don't retry if we've reached max retries
    if (
      config &&
      config.retryCount < RETRY_COUNT &&
      (error.code === 'ECONNABORTED' || 
       error.message === 'Network Error' || 
       (error.response && error.response.status >= 500))
    ) {
      config.retryCount += 1;
      
      // Exponential backoff
      const backoff = new Promise((resolve) => {
        setTimeout(() => {
          resolve();
        }, RETRY_DELAY * Math.pow(2, config.retryCount - 1));
      });

      await backoff;
      return api(config);
    }

    if (error.response && error.response.status === 401) {
      // Ignore 401 from checkAuth to allow non-logged in users to visit /register
      if (error.config.url && error.config.url.includes('/auth/users/me')) {
        return Promise.reject(error);
      }

      // Redirect to login or clear auth state
      // We can't use hooks here directly, but we can access the store
      // useAuthStore.getState().logout(); // Avoid circular dependency
      window.location.href = '/login';
    }
    // Dispatch global error event for UI notification
    const errorMessage = error.response?.data?.detail || error.message || 'Unknown error occurred';
    window.dispatchEvent(new CustomEvent('api-error', { 
        detail: { 
            message: errorMessage,
            status: error.response?.status,
            url: error.config?.url
        } 
    }));

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

// Get node details
export const getNodeDetails = (networkId, nodeId) => 
  api.get(`/networks/${networkId}/nodes/${nodeId}`);

// Create chat
export const createChat = (name) => api.post('/chat', { name });

// Update chat (e.g. rename)
export const updateChat = (chatId, data) => api.patch(`/chat/${chatId}`, data);

// Process message
export const processMessage = (chatId, content) =>
  api.post(`/chat/${chatId}/process`, {
    message: { content }
  });

export const uploadGraphML = async (chatId, file) => {
  const formData = new FormData();
  formData.append('file', file);

  return api.post(`/chat/${chatId}/upload`, formData, {
    headers: {
      'Content-Type': undefined
    }
  });
};

export default api;
