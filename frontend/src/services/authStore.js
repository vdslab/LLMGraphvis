/**
 * @file Zustand store for managing authentication state.
 * @module stores/auth
 */
import { create } from 'zustand';
import { authAPI } from './api';

/**
 * Zustand store for authentication.
 *
 * @returns {object} The authentication store.
 */
const useAuthStore = create((set) => ({
  /** @type {object|null} The authenticated user. */
  user: null,
  /** @type {string|null} The authentication token. */
  token: localStorage.getItem('token') || null,
  /** @type {boolean} Whether the user is authenticated. */
  isAuthenticated: !!localStorage.getItem('token'),
  isLoading: false,
  error: null,

  /**
   * Logs in a user.
   *
   * @param {string} username - The user's username.
   * @param {string} password - The user's password.
   * @returns {Promise<boolean>} Whether the login was successful.
   */
  login: async (username, password) => {
    set({ isLoading: true, error: null });
    try {
      console.log("Attempting to login with username:", username);
      const response = await authAPI.login(username, password);
      const { access_token } = response.data;
      
      console.log("Login successful, token received");
      // Store token in localStorage
      localStorage.setItem('token', access_token);
      
      // Get user info
      console.log("Fetching user info with token");
      const userResponse = await authAPI.getCurrentUser();
      console.log("User info received:", userResponse.data);
      
      set({ 
        token: access_token,
        user: userResponse.data,
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
      
      return true;
    } catch (error) {
      console.error("Login failed:", error);
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || 'Login failed'
      });
      return false;
    }
  },

  /**
   * Registers a new user.
   *
   * @param {string} username - The user's username.
   * @param {string} password - The user's password.
   * @returns {Promise<boolean>} Whether the registration was successful.
   */
  register: async (username, password) => {
    set({ isLoading: true, error: null });
    try {
      console.log("Attempting to register with username:", username);
      const registerResponse = await authAPI.register(username, password);
      console.log("Registration successful:", registerResponse.data);
      
      // Login after successful registration
      console.log("Attempting to login after registration");
      return await useAuthStore.getState().login(username, password);
    } catch (error) {
      console.error("Registration failed:", error);
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || 'Registration failed'
      });
      return false;
    }
  },

  /**
   * Logs out the current user.
   */
  logout: () => {
    localStorage.removeItem('token');
    set({ 
      user: null,
      token: null,
      isAuthenticated: false
    });
  },

  /**
   * Checks the authentication status of the user.
   *
   * @returns {Promise<boolean>} Whether the user is authenticated.
   */
  checkAuth: async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      console.log("No token found in localStorage");
      set({ 
        isAuthenticated: false, 
        user: null,
        token: null,
        isLoading: false,
        error: null
      });
      return false;
    }

    console.log("Token found in localStorage, checking validity");
    set({ isLoading: true, error: null });
    try {
      console.log("Making request to /auth/users/me with token");
      const response = await authAPI.getCurrentUser();
      console.log("User authenticated successfully:", response.data);
      set({ 
        user: response.data,
        token: token, // Ensure token is set in state
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
      return true;
    } catch (error) {
      console.error("Authentication check failed:", error);
      console.error("Error status:", error.response?.status);
      console.error("Error data:", error.response?.data);
      
      // Clear token from localStorage
      localStorage.removeItem('token');
      
      set({ 
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: error.response?.data?.detail || "Authentication failed"
      });
      return false;
    }
  }
}));

export default useAuthStore;
