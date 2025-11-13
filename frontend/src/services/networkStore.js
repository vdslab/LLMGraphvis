/**
 * @file Zustand store for managing network state.
 * @module stores/network
 */
import { create } from "zustand";
import { networkAPI } from "./api";
import useChatStore from "./chatStore";

/**
 * Generates a color based on a centrality value.
 *
 * @param {number} value - The centrality value.
 * @param {number} maxValue - The maximum centrality value.
 * @returns {string} The RGB color string.
 */
const getCentralityColor = (value, maxValue) => {
  // Generate a color from blue (low) to red (high)
  const ratio = value / maxValue;
  const r = Math.floor(255 * ratio);
  const b = Math.floor(255 * (1 - ratio));
  return `rgb(${r}, 70, ${b})`;
};

/**
 * Zustand store for network data.
 *
 * @returns {object} The network store.
 */
const useNetworkStore = create((set, get) => ({
  /** @type {Array<object>} The nodes of the network. */
  nodes: [],
  /** @type {Array<object>} The edges of the network. */
  edges: [],
  /** @type {string} The current layout algorithm. */
  layout: "spring",
  /** @type {object} The parameters for the current layout algorithm. */
  layoutParams: {},
  /** @type {Array<object>} The positions of the nodes. */
  positions: [],
  /** @type {object|null} The current centrality values. */
  centrality: null,
  /** @type {string|null} The type of the current centrality metric. */
  centralityType: null,
  /** @type {boolean} Whether the network is currently loading. */
  isLoading: false,
  /** @type {string|null} The current error message. */
  error: null,
  /** @type {string|null} The success message. */
  successMessage: null,
  /** @type {object|null} The current layout recommendation. */
  recommendation: null,
  /** @type {object} The visual properties of the network. */
  visualProperties: {
    node_size: 5,
    node_color: "#1d4ed8",
    edge_width: 1,
    edge_color: "#94a3b8",
  },

  /**
   * Sets the network data.
   *
   * @param {Array<object>} nodes - The nodes of the network.
   * @param {Array<object>} edges - The edges of the network.
   */
  setNetworkData: (nodes, edges) => {
    set({ nodes, edges });
  },

  /**
   * Sets the layout algorithm.
   *
   * @param {string} layout - The name of the layout algorithm.
   */
  setLayout: (layout) => {
    set({ layout });
  },

  /**
   * Sets the node positions.
   *
   * @param {Array<object>} positions - The positions of the nodes.
   */
  setPositions: (positions) => {
    set({ positions });
  },

  /**
   * Sets the layout parameters.
   *
   * @param {object} layoutParams - The parameters for the layout algorithm.
   */
  setLayoutParams: (layoutParams) => {
    set({ layoutParams });
  },

  /**
   * Calculates the layout of the network.
   *
   * @returns {Promise<boolean>} Whether the layout was calculated successfully.
   */
  calculateLayout: async () => {
    const { layout, layoutParams } = get();
    const conversationId = useChatStore.getState().currentConversationId;
    
    if (!conversationId) {
      console.log("No conversation selected, skipping layout calculation");
      return false;
    }

    set({ isLoading: true, error: null });
    
    try {
      // Get current network data
      const networkId = conversationId;
      const cytoscapeResponse = await networkAPI.getNetworkCytoscape(networkId);
      const cytoData = cytoscapeResponse.data;
      
      if (!cytoData || !cytoData.elements) {
        throw new Error("Failed to retrieve network data");
      }
      
      // Call NetworkXMCP to calculate layout
      const response = await networkAPI.calculateLayout(networkId, layout, layoutParams);
      
      if (response.data && response.data.result && response.data.result.success) {
        const positions = response.data.result.positions;
        
        // Update positions in the store
        const updatedPositions = Object.keys(positions).map(nodeId => ({
          id: nodeId,
          x: positions[nodeId].x,
          y: positions[nodeId].y,
          size: 5,
          color: "#1d4ed8"
        }));
        
        set({
          positions: updatedPositions,
          isLoading: false,
          error: null
        });
        
        return true;
      } else {
        throw new Error("Layout calculation failed");
      }
    } catch (error) {
      console.error("Error calculating layout:", error);
      set({
        isLoading: false,
        error: error.message || "Failed to calculate layout"
      });
      return false;
    }
  },

  /**
   * Applies the current layout to the network.
   *
   * @returns {Promise<boolean>} Whether the layout was applied successfully.
   */
  applyLayout: async () => {
    return await get().calculateLayout();
  },

  /**
   * Loads a sample network.
   *
   * @returns {Promise<boolean>} Whether the sample network was loaded successfully.
   */
  loadSampleNetwork: async () => {
    console.log("Generating static sample network");
    set({ isLoading: true, error: null });
    
    try {
      const sampleNodes = [];
      const sampleEdges = [];
      const samplePositions = [];
      
      // Center node
      sampleNodes.push({
        id: "0",
        label: "Center Node",
      });
      
      samplePositions.push({
        id: "0",
        label: "Center Node",
        x: 0,
        y: 0,
        size: 8,
        color: "#1d4ed8",
      });
      
      // 10 satellite nodes
      for (let i = 1; i <= 10; i++) {
        sampleNodes.push({
          id: i.toString(),
          label: `Node ${i}`,
        });
        
        sampleEdges.push({
          source: "0",
          target: i.toString(),
        });
        
        const angle = (i - 1) * (2 * Math.PI / 10);
        samplePositions.push({
          id: i.toString(),
          label: `Node ${i}`,
          x: Math.cos(angle),
          y: Math.sin(angle),
          size: 5,
          color: "#1d4ed8",
        });
      }
      
      set({
        nodes: sampleNodes,
        edges: sampleEdges,
        positions: samplePositions,
        layout: "spring",
        isLoading: false,
        error: null,
      });
      
      return true;
    } catch (error) {
      console.error("Error generating static sample network:", error);
      set({
        isLoading: false,
        error: "Failed to generate sample network",
      });
      return false;
    }
  },

  /**
   * 可視化データを取得して更新する
   *
   * @returns {Promise<boolean>} 取得成功か否か
   */
  fetchVisData: async () => {
    const { currentConversationId } = useChatStore.getState();
    if (!currentConversationId) {
      set({ error: "アクティブな会話がありません。" });
      return false;
    }
    
    const networkId = currentConversationId;
    
    try {
      const response = await networkAPI.getNetworkVisData(networkId);
      const visData = response.data;
      
      if (visData && visData.nodes && visData.links) {
        set({
          nodes: visData.nodes,
          edges: visData.links,
          positions: visData.nodes.map(node => ({
            id: node.id,
            x: node.x,
            y: node.y,
            size: node.size,
            color: node.color,
            label: node.label || node.id
          })),
          error: null
        });
        return true;
      } else {
        throw new Error("無効な可視化データを受信しました");
      }
    } catch (error) {
      console.error("可視化データの取得エラー:", error);
      set({
        error: error.message || "可視化データの取得に失敗しました"
      });
      return false;
    }
  },

  /**
   * 次数中心性をノードサイズに適用する
   *
   * @param {object} [mapping] - マッピングパラメータ (e.g. {min_size: 5, max_size: 20})
   * @returns {Promise<boolean>} 適用成功か否か
   */
  applyDegreeCentralityToSize: async (mapping = null) => {
    const { currentConversationId } = useChatStore.getState();
    if (!currentConversationId) {
      set({ error: "アクティブな会話がありません。" });
      return false;
    }
    
    const networkId = currentConversationId;
    
    set({ isLoading: true, error: null, successMessage: null });
    
    try {
      // 次数中心性を適用
      await networkAPI.applyDegreeCentralityToSize(networkId, mapping);
      
      // 可視化データを再取得して更新
      const fetchSuccess = await get().fetchVisData();
      
      set({
        isLoading: false,
        successMessage: fetchSuccess ? "次数中心性をノードサイズに反映しました" : null
      });
      
      return fetchSuccess;
    } catch (error) {
      console.error("次数中心性適用エラー:", error);
      set({
        isLoading: false,
        error: error.response?.data?.message || error.message || "次数中心性の適用に失敗しました",
        successMessage: null
      });
      return false;
    }
  },

  /**
   * Gets a layout recommendation from the API.
   *
   * @param {string} description - A description of the network.
   * @param {string} purpose - The purpose of the visualization.
   * @returns {Promise<boolean>} Whether the recommendation was retrieved successfully.
   */
  getLayoutRecommendation: async (description, purpose) => {
    set({ isLoading: true, error: null });
    try {
      const response = await networkAPI.getLayoutRecommendation(description, purpose);
      const result = response.data;
      
      if (result && result.success) {
        set({
          recommendation: result,
          isLoading: false,
          error: null
        });
        return true;
      } else {
        throw new Error("Failed to get layout recommendation");
      }
    } catch (error) {
      console.error("Error getting layout recommendation:", error);
      set({
        isLoading: false,
        error: error.message || "Failed to get layout recommendation"
      });
      return false;
    }
  },

  /**
   * Applies the recommended layout.
   *
   * @returns {Promise<boolean>} Whether the layout was applied successfully.
   */
  applyRecommendedLayout: async () => {
    const { recommendation } = get();
    if (!recommendation) {
      set({ error: "No recommendation available" });
      return false;
    }
    
    set({ 
      layout: recommendation.recommended_layout,
      layoutParams: recommendation.recommended_parameters || {}
    });
    
    return await get().calculateLayout();
  },

  /**
   * Applies centrality values to the network nodes.
   *
   * @param {object} centralityValues - The centrality values.
   * @param {string} centralityType - The type of centrality.
   */
  applyCentralityValues: (centralityValues, centralityType) => {
    const maxValue = Math.max(...Object.values(centralityValues), 1);
    const updatedPositions = get().positions.map((node) => {
      const value = centralityValues[node.id] || 0;
      const normalizedSize = 5 + (value / maxValue) * 15;
      return {
        ...node,
        size: normalizedSize,
        color: getCentralityColor(value, maxValue),
      };
    });
    set({
      positions: updatedPositions,
      centrality: centralityValues,
      centralityType,
    });
  },
 
  /**
   * Clears all network data.
   */
  clearData: () => {
    set({
      nodes: [],
      edges: [],
      positions: [],
      centrality: null,
      centralityType: null,
      recommendation: null,
      error: null,
    });
  },

  /**
   * Uploads a network file.
   *
   * @param {File} file - The file to upload.
   * @returns {Promise<{success: boolean, error?: string}>} The result of the upload.
   */
  uploadNetworkFile: async (file) => {
    set({ isLoading: true, error: null });
    try {
      const conversationId = useChatStore.getState().currentConversationId;
      console.log(`Uploading file. Conversation ID: ${conversationId}`);

      const response = await networkAPI.uploadGraphML(file, conversationId);
      const result = response.data;

      console.log("Upload response from API:", result);

      if (result && result.network_id && result.conversation_id) {
        console.log("File uploaded successfully. New data:", result);

        useChatStore.getState().setCurrentConversationId(result.conversation_id);
        
        useChatStore.getState().addMessage({
          role: "assistant",
          content: `ファイル "${file.name}" が正常にアップロードされ、新しいネットワークが作成されました。`,
          timestamp: new Date().toISOString(),
        });

        const cytoscapeResponse = await networkAPI.getNetworkCytoscape(result.network_id);
        const cytoData = cytoscapeResponse.data;

        if (cytoData && cytoData.elements) {
          set({
            nodes: cytoData.elements.nodes.map(n => n.data),
            edges: cytoData.elements.edges.map(e => e.data),
            positions: cytoData.elements.nodes.map(n => ({ ...n.data, ...n.position })),
            isLoading: false,
            error: null,
          });
          return { success: true };
        } else {
          throw new Error("Failed to retrieve valid Cytoscape data after upload.");
        }
      } else {
        const errorMessage = result.detail || "Unknown error during file upload process.";
        console.error("File upload failed:", errorMessage);
        throw new Error(errorMessage);
      }
    } catch (error) {
      const errorMessage =
        error.response?.data?.detail ||
        error.message ||
        "An unknown error occurred during file upload.";

      console.error("Caught error in uploadNetworkFile:", errorMessage);
      
      set({
        isLoading: false,
        error: errorMessage,
      });

      return {
        success: false,
        error: errorMessage,
      };
    }
  },

  /**
   * Exports the network as a GraphML file.
   *
   * @returns {Promise<Blob|null>} The exported GraphML data.
   */
  exportAsGraphML: async () => {
    const { currentConversationId } = useChatStore.getState();
    if (!currentConversationId) {
      set({ error: "No active conversation selected." });
      return null;
    }
    const networkId = currentConversationId; 

    set({ isLoading: true, error: null });
    try {
      console.log("Exporting network as GraphML");
      const response = await networkAPI.exportNetworkAsGraphML(networkId);
      set({ isLoading: false, error: null });
      return response.data;
    } catch (error) {
      console.error("Failed to export network as GraphML:", error);
      set({
        isLoading: false,
        error: error.message || "Failed to export network as GraphML",
      });
      return null;
    }
  },

  /**
   * Gets information about the current network.
   *
   * @returns {Promise<object|null>} Information about the network.
   */
  getNetworkInfo: async () => {
    const { currentConversationId } = useChatStore.getState();
    if (!currentConversationId) {
      set({ error: "No active conversation selected." });
      return null;
    }
    const networkId = currentConversationId;

    set({ isLoading: true, error: null });
    try {
      const response = await networkAPI.getNetworkCytoscape(networkId);
      const cytoData = response.data;
      if (cytoData && cytoData.elements) {
        const nodes = cytoData.elements.nodes.map(n => n.data);
        const edges = cytoData.elements.edges.map(e => e.data);
        const positions = cytoData.elements.nodes.map(n => ({ ...n.data, ...n.position }));
        set({
          nodes,
          edges,
          positions,
          isLoading: false,
          error: null,
        });
        return {
          success: true,
          network_info: {
            has_network: true,
            num_nodes: nodes.length,
            num_edges: edges.length,
          },
        };
      } else {
        throw new Error("Failed to retrieve valid Cytoscape data.");
      }
    } catch (error) {
      console.error("Error fetching network info:", error);
      set({ isLoading: false, error: error.message });
      return null;
    }
  },
}));

export default useNetworkStore;
