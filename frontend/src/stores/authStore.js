import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../services/api';

export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      login: async (username, password) => {
        // Fix: Use proper form-data format for OAuth2PasswordRequestForm
        const params = new URLSearchParams();
        params.append('username', username);
        params.append('password', password);
        
        await api.post('/auth/token', params, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        });
        
        // After successful login, fetch user details
        const user = await api.get('/auth/users/me');
        set({ user: user.data, isAuthenticated: true, isLoading: false });
      },

      register: async (username, password) => {
        await api.post('/auth/register', { username, password });
        
        // Auto login after register
        const user = await api.get('/auth/users/me');
        set({ user: user.data, isAuthenticated: true, isLoading: false });
      },

      logout: async () => {
        try {
          await api.post('/auth/logout'); 
        } catch (e) {
          console.error("Logout failed", e);
        }
        set({ user: null, isAuthenticated: false, isLoading: false });
        // Clear everything
        localStorage.removeItem('auth-storage');
      },

      checkAuth: async () => {
        try {
          // If we have state from persistence, we are "optimistically" authenticated
          // but we still verify with the backend
          const user = await api.get('/auth/users/me');
          set({ user: user.data, isAuthenticated: true });
        } catch (error) {
          set({ user: null, isAuthenticated: false });
        } finally {
          set({ isLoading: false });
        }
      }
    }),
    {
      name: 'auth-storage', // name of the item in the storage (must be unique)
      partialize: (state) => ({ 
        user: state.user, 
        isAuthenticated: state.isAuthenticated 
      }), // Only persist user and auth status, not loading state
    }
  )
);
