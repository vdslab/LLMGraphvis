import { create } from 'zustand';
import api from '../services/api';

export const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (username, password) => {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    
    // Explicitly set content type for this request to override default JSON
    await api.post('/auth/token', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
    
    // After successful login, fetch user details
    const user = await api.get('/auth/users/me');
    set({ user: user.data, isAuthenticated: true });
  },

  register: async (username, password) => {
    await api.post('/auth/register', { username, password });
    // Auto login after register? Or redirect to login.
    // Spec says: "Login after screen transition" (implied)
  },

  logout: async () => {
    try {
      await api.post('/auth/logout'); 
    } catch (e) {
      console.error("Logout failed", e);
    }
    set({ user: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    try {
      const user = await api.get('/auth/users/me');
      set({ user: user.data, isAuthenticated: true });
    } catch (error) {
      set({ user: null, isAuthenticated: false });
    } finally {
      set({ isLoading: false });
    }
  }
}));
