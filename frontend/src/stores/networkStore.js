import { create } from 'zustand';

export const useNetworkStore = create((set) => ({
  networkId: null,
  nodes: [],
  links: [],
  legend: null,

  setNetworkData: (data) => {
    // data: { nodes: [], links: [], legend: {} }
    set({ nodes: data?.nodes || [], links: data?.links || [], legend: data?.legend || null });
  },

  setNetworkId: (id) => set({ networkId: id }),

  reset: () => set({ networkId: null, nodes: [], links: [], legend: null })
}));
