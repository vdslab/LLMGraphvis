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

export default api;
