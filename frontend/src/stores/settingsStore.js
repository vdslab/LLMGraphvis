import { create } from 'zustand';
import {
  changePassword as changePasswordAPI,
  getUserSettings,
  updateUserSettings,
} from '../services/api';

// The signed-in user's settings (ADR 0026). defaultProvider/defaultModel are
// what an unpinned chat runs on; null means the server default.
export const useSettingsStore = create((set, get) => ({
  settings: null,
  status: 'idle',

  fetchSettings: async ({ force = false } = {}) => {
    if (!force && get().status === 'success') return get().settings;
    set({ status: 'loading' });
    try {
      const res = await getUserSettings();
      set({ settings: res.data, status: 'success' });
      return res.data;
    } catch (error) {
      set({ status: 'error' });
      throw error;
    }
  },

  // Both values, or both null to fall back to the server default.
  setDefaultModel: async (provider, model) => {
    const res = await updateUserSettings({
      default_provider: provider,
      default_model: model,
    });
    set({ settings: res.data, status: 'success' });
    return res.data;
  },

  // The backend signs out every other session and re-issues this one's cookie.
  changePassword: async (currentPassword, newPassword) => {
    await changePasswordAPI(currentPassword, newPassword);
  },

  reset: () => set({ settings: null, status: 'idle' }),
}));
