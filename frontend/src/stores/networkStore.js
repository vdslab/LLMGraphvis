import { create } from 'zustand';

export const useNetworkStore = create((set) => ({
  networkId: null,
  nodes: [],
  links: [],
  legend: null,
  layoutQuality: null,
  labelStyle: null,
  viewport: null,

  setNetworkData: (data) => {
    // Replace all facts about the drawing together; keeping an old quality
    // report after a size or network change would describe a different view.
    set({
      nodes: data?.nodes || [],
      links: data?.links || [],
      legend: data?.legend || null,
      layoutQuality: data?.layout_quality || null,
      labelStyle: data?.label_style || null,
      // A one-shot camera instruction; NetworkGraph applies each nonce once.
      viewport: data?.viewport || null,
    });
  },

  setNetworkId: (id) => set({ networkId: id }),

  reset: () => set({
    networkId: null, nodes: [], links: [], legend: null, layoutQuality: null,
    labelStyle: null, viewport: null,
  })
}));
