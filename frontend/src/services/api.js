/**
 * @file API service for interacting with the backend.
 * @module services/api
 */
import axios from "axios";

// Direct connection to API server
// Using localhost:8000 to connect directly to the API server
const DIRECT_API_URL = "http://localhost:8000";
const API_URL = DIRECT_API_URL;

console.log("Using API URL:", API_URL);

// Add auth token to requests
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      // Ensure the Authorization header is set correctly
      config.headers = {
        ...config.headers,
        Authorization: `Bearer ${token}`
      };
      console.log("Adding token to request:", config.url, "Token:", token.substring(0, 10) + "...");
      console.log("Full headers:", JSON.stringify(config.headers));
    } else {
      console.log("No token found for request:", config.url);
      
      // Check if we're on a protected route and redirect to login if needed
      if (window.location.pathname !== '/' && 
          window.location.pathname !== '/login' && 
          window.location.pathname !== '/register') {
        console.log("Protected route detected without token, redirecting to login");
        // We'll handle this in the response interceptor
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Add response interceptor for debugging
axios.interceptors.response.use(
  (response) => {
    console.log("Response from:", response.config.url, "Status:", response.status);
    return response;
  },
  (error) => {
    console.error("Error response:", error.config?.url, "Status:", error.response?.status);
    console.error("Error details:", error.response?.data);
    
    // Handle 401 errors globally
    if (error.response?.status === 401) {
      console.error("Authentication error detected, clearing token and redirecting to login");
      localStorage.removeItem('token');
      
      // Only redirect if we're not already on the login page
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);

/**
 * API endpoints for authentication.
 * @namespace authAPI
 */
export const authAPI = {
  /**
   * Logs in a user.
   * @param {string} username - The user's username.
   * @param {string} password - The user's password.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  login: (username, password) => {
    console.log("Login request with username:", username);
    return axios.post(
      `${API_URL}/auth/token`,
      `username=${username}&password=${password}`,
      {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      },
    );
  },
  /**
   * Registers a new user.
   * @param {string} username - The user's username.
   * @param {string} password - The user's password.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  register: (username, password) => {
    console.log("Register request with username:", username);
    return axios.post(`${API_URL}/auth/register`, { username, password });
  },
  /**
   * Gets the current authenticated user.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  getCurrentUser: () => {
    console.log("Getting current user");
    return axios.get(`${API_URL}/auth/users/me`);
  },
};

/**
 * API endpoints for network data.
 * @namespace networkAPI
 */
export const networkAPI = {
  /**
   * Gets all networks.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  getNetworks: () => {
    console.log("Getting all networks");
    return axios.get(`${API_URL}/network/`);
  },
  /**
   * Gets a specific network by ID.
   * @param {string} networkId - The ID of the network.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  getNetwork: (networkId) => {
    console.log("Getting network:", networkId);
    return axios.get(`${API_URL}/network/${networkId}`);
  },
  /**
   * Creates a new network.
   * @param {object} networkData - The data for the new network.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  createNetwork: (networkData) => {
    console.log("Creating network with data:", networkData);
    return axios.post(`${API_URL}/network/`, networkData);
  },
  /**
   * Updates an existing network.
   * @param {string} networkId - The ID of the network to update.
   * @param {object} networkData - The updated network data.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  updateNetwork: (networkId, networkData) => {
    console.log("Updating network:", networkId);
    return axios.put(`${API_URL}/network/${networkId}`, networkData);
  },
  /**
   * Deletes a network.
   * @param {string} networkId - The ID of the network to delete.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  deleteNetwork: (networkId) => {
    console.log("Deleting network:", networkId);
    return axios.delete(`${API_URL}/network/${networkId}`);
  },
  /**
   * Gets a network in Cytoscape.js format.
   * @param {string} networkId - The ID of the network.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  getNetworkCytoscape: (networkId) => {
    console.log("Getting network in Cytoscape format:", networkId);
    return axios.get(`${API_URL}/network/${networkId}/cytoscape`);
  },
  /**
   * Uploads a GraphML file.
   * @param {File} file - The GraphML file to upload.
   * @param {string} [conversationId] - The ID of the conversation to associate the network with.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  uploadGraphML: (file, conversationId = null) => {
    const formData = new FormData();
    formData.append("file", file);

    let url = `${API_URL}/network/upload`;
    if (conversationId) {
      url = `${API_URL}/network/${conversationId}/upload`;
    }
    
    console.log(`Uploading GraphML to ${url}`);
    return axios.post(url, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },
  /**
   * Exports a network as a GraphML file.
   * @param {string} networkId - The ID of the network to export.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  exportNetworkAsGraphML: (networkId) => {
    console.log("Exporting network as GraphML:", networkId);
    return axios.get(`${API_URL}/network/${networkId}/export`, {
      responseType: 'blob',
    });
  },
  /**
   * Calculates the layout for a network.
   * @param {string} networkId - The ID of the network.
   * @param {string} layoutType - The type of layout to apply.
   * @param {object} [layoutParams] - Parameters for the layout algorithm.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  calculateLayout: (networkId, layoutType, layoutParams = {}) => {
    console.log("Calculating layout for network:", networkId, "Type:", layoutType);
    return axios.post(`${API_URL}/network/${networkId}/layout`, {
      layout_type: layoutType,
      layout_params: layoutParams
    });
  },
  /**
   * Gets a layout recommendation.
   * @param {string} description - The description of the network.
   * @param {string} purpose - The purpose of the visualization.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  getLayoutRecommendation: (description, purpose) => {
    console.log("Getting layout recommendation");
    return axios.post(`${API_URL}/chat/recommend-layout`, {
      description,
      purpose
    });
  },
};

/**
 * API endpoints for network chat.
 * @namespace networkChatAPI
 */
export const networkChatAPI = {
  /**
   * Gets all conversations.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  getConversations: () => {
    console.log("Getting all conversations");
    return axios.get(`${API_URL}/chat/conversations`);
  },
  /**
   * Gets all messages for a conversation.
   * @param {string} conversationId - The ID of the conversation.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  getMessages: (conversationId) => {
    console.log("Getting messages for conversation:", conversationId);
    return axios.get(`${API_URL}/chat/conversations/${conversationId}/messages`);
  },
  /**
   * Sends a message to a conversation.
   * @param {string} conversationId - The ID of the conversation.
   * @param {string} message - The message to send.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  sendMessage: (conversationId, message) => {
    console.log("Sending message to conversation:", conversationId, message);
    return axios.post(`${API_URL}/chat/conversations/${conversationId}/messages`, {
      content: message,
      role: "user"
    });
  },
  /**
   * Creates a new conversation.
   * @param {string} [title="New Conversation"] - The title of the conversation.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  createConversation: (title = "New Conversation") => {
    console.log("Creating new conversation with title:", title);
    return axios.post(`${API_URL}/chat/conversations`, { title });
  },
  /**
   * Deletes a conversation.
   * @param {string} conversationId - The ID of the conversation to delete.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  deleteConversation: (conversationId) => {
    console.log("Deleting conversation:", conversationId);
    return axios.delete(`${API_URL}/chat/conversations/${conversationId}`);
  },
  /**
   * Processes a chat message.
   * @param {object} payload - The chat message payload.
   * @returns {Promise<axios.AxiosResponse>} The axios response.
   */
  processChatMessage: (payload) => {
    console.log("Processing chat message via API:", payload);
    // APIサーバーを経由してチャットメッセージを処理
    return axios.post(`${API_URL}/chat/process`, payload);
  }
};
