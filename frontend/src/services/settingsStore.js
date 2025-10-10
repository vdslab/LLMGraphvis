import { create } from "zustand";
import { settingsAPI } from "./api";

const useSettingsStore = create((set, get) => ({
  // State
  llmSettings: {
    provider: "google",
    has_google_api_key: false,
    has_openai_api_key: false,
    openai_model: "gpt-4o",
    available_providers: ["google", "openai"],
  },
  llmStatus: {
    provider: "google",
    status: "unknown",
    has_required_keys: false,
    message: "",
  },
  isLoading: false,
  error: null,
  isUpdating: false,
  updateSuccess: false,

  // Actions
  fetchLLMSettings: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await settingsAPI.getLLMProviderSettings();
      set({
        llmSettings: response.data,
        isLoading: false,
      });
      return response.data;
    } catch (error) {
      const errorMessage =
        error.response?.data?.detail || "Failed to fetch LLM settings";
      set({
        error: errorMessage,
        isLoading: false,
      });
      throw error;
    }
  },

  updateLLMSettings: async (settings) => {
    set({ isUpdating: true, error: null, updateSuccess: false });
    try {
      const response = await settingsAPI.updateLLMProviderSettings(settings);
      set({
        llmSettings: response.data,
        isUpdating: false,
        updateSuccess: true,
      });

      // Clear success message after 3 seconds
      setTimeout(() => {
        set({ updateSuccess: false });
      }, 3000);

      return response.data;
    } catch (error) {
      const errorMessage =
        error.response?.data?.detail || "Failed to update LLM settings";
      set({
        error: errorMessage,
        isUpdating: false,
        updateSuccess: false,
      });
      throw error;
    }
  },

  fetchLLMStatus: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await settingsAPI.getLLMProviderStatus();
      set({
        llmStatus: response.data,
        isLoading: false,
      });
      return response.data;
    } catch (error) {
      const errorMessage =
        error.response?.data?.detail || "Failed to fetch LLM status";
      set({
        error: errorMessage,
        isLoading: false,
      });
      throw error;
    }
  },

  // Helper methods
  clearError: () => set({ error: null }),
  clearUpdateSuccess: () => set({ updateSuccess: false }),

  // Reset store
  reset: () =>
    set({
      llmSettings: {
        provider: "google",
        has_google_api_key: false,
        has_openai_api_key: false,
        openai_model: "gpt-4o",
        available_providers: ["google", "openai"],
      },
      llmStatus: {
        provider: "google",
        status: "unknown",
        has_required_keys: false,
        message: "",
      },
      isLoading: false,
      error: null,
      isUpdating: false,
      updateSuccess: false,
    }),
}));

export default useSettingsStore;
