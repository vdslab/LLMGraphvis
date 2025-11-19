import { create } from 'zustand';
import api from '../services/api';

export const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (username, password) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    await api.post('/auth/token', formData);
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
    // Call logout endpoint if exists to clear cookie
    // await api.post('/auth/logout'); 
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
