import { create } from 'zustand';

export const useNetworkStore = create((set) => ({
  networkId: null,
  nodes: [],
  links: [],
  
  setNetworkData: (data) => {
    // data: { nodes: [], links: [] }
    set({ nodes: data.nodes, links: data.links });
  },
  
  setNetworkId: (id) => set({ networkId: id }),
  
  reset: () => set({ networkId: null, nodes: [], links: [] })
}));
