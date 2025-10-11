import { create } from "zustand";
import { networkAPI } from "./api";
import useChatStore from "./chatStore";

const useNetworkStore = create((set, get) => ({
  nodes: [],
  edges: [],
  layout: "spring",
  layoutParams: {},
  positions: [],
  centrality: null,
  centralityType: null,
  centralityInfo: null, // Store information about applied centrality calculations
  isLoading: false,
  error: null,
  recommendation: null,
  visualProperties: {
    node_size: 5,
    node_color: "#1d4ed8",
    edge_width: 1,
    edge_color: "#94a3b8",
  },

  // Set network data
  setNetworkData: (nodes, edges) => {
    set({ nodes, edges });
  },

  // Set layout type
  setLayout: (layout) => {
    set({ layout });
  },

  // Set positions
  setPositions: (positions) => {
    set({ positions });
  },

  // Set layout parameters
  setLayoutParams: (layoutParams) => {
    set({ layoutParams });
  },

  // Calculate layout using API
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
      const response = await networkAPI.calculateLayout(
        networkId,
        layout,
        layoutParams,
      );

      if (
        response.data &&
        response.data.result &&
        response.data.result.success
      ) {
        const positions = response.data.result.positions;

        // Update positions in the store
        const updatedPositions = Object.keys(positions).map((nodeId) => ({
          id: nodeId,
          x: positions[nodeId].x,
          y: positions[nodeId].y,
          size: 5,
          color: "#1d4ed8",
        }));

        set({
          positions: updatedPositions,
          isLoading: false,
          error: null,
        });

        return true;
      } else {
        throw new Error("Layout calculation failed");
      }
    } catch (error) {
      console.error("Error calculating layout:", error);
      set({
        isLoading: false,
        error: error.message || "Failed to calculate layout",
      });
      return false;
    }
  },

  // Apply layout using MCP client with GraphML
  applyLayout: async () => {
    return await get().calculateLayout();
  },

  // Load sample network using API
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

        const angle = (i - 1) * ((2 * Math.PI) / 10);
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

  // Get layout recommendation
  getLayoutRecommendation: async (description, purpose) => {
    set({ isLoading: true, error: null });
    try {
      const response = await networkAPI.getLayoutRecommendation(
        description,
        purpose,
      );
      const result = response.data;

      if (result && result.success) {
        set({
          recommendation: result,
          isLoading: false,
          error: null,
        });
        return true;
      } else {
        throw new Error("Failed to get layout recommendation");
      }
    } catch (error) {
      console.error("Error getting layout recommendation:", error);
      set({
        isLoading: false,
        error: error.message || "Failed to get layout recommendation",
      });
      return false;
    }
  },

  // Apply recommended layout
  applyRecommendedLayout: async () => {
    const { recommendation } = get();
    if (!recommendation) {
      set({ error: "No recommendation available" });
      return false;
    }

    set({
      layout: recommendation.recommended_layout,
      layoutParams: recommendation.recommended_parameters || {},
    });

    return await get().calculateLayout();
  },

  // Apply centrality values directly to graph data for backward compatibility
  applyCentralityValues: (centrality_values, centrality_type) => {
    set((state) => {
      console.log(
        `Applying ${centrality_type} centrality values:`,
        centrality_values,
      );

      // Update graph data with centrality values
      const updatedGraphData = { ...state.graphData };
      if (updatedGraphData.nodes) {
        updatedGraphData.nodes = updatedGraphData.nodes.map((node) => ({
          ...node,
          [`${centrality_type}_centrality`]: centrality_values[node.id] || 0,
        }));
      }

      return {
        ...state,
        graphData: updatedGraphData,
      };
    });
  },

  // Apply visualization data from two-stage centrality processing
  applyCentralityVisualizationData: (
    visualization_data,
    centrality_type,
    calculation_id,
  ) => {
    set((state) => {
      console.log(
        `🎨 Applying ${centrality_type} centrality visualization data:`,
        visualization_data,
      );

      // Update positions array with centrality visualization
      const updatedPositions = state.positions.map((node) => {
        const nodeId = node.id;
        const nodeVizData = visualization_data[nodeId];

        if (nodeVizData) {
          const {
            centrality_value,
            color,
            size,
            importance_level,
            percentile,
          } = nodeVizData;

          console.log(
            `Updating node ${nodeId}: size=${size}, color=${color}, centrality=${centrality_value}`,
          );

          return {
            ...node,
            // Update visual properties
            color: color,
            size: size,
            // Store centrality information
            [`${centrality_type}_centrality`]: centrality_value,
            centrality_value: centrality_value,
            importance_level: importance_level,
            percentile: percentile,
            // Store original properties for potential restoration
            originalColor: node.originalColor || node.color || "#1d4ed8",
            originalSize: node.originalSize || node.size || 5,
          };
        }

        return node;
      });

      // Also update nodes array if it exists
      const updatedNodes = state.nodes.map((node) => {
        const nodeId = node.id;
        const nodeVizData = visualization_data[nodeId];

        if (nodeVizData) {
          const { centrality_value, importance_level, percentile } =
            nodeVizData;

          return {
            ...node,
            [`${centrality_type}_centrality`]: centrality_value,
            centrality_value: centrality_value,
            importance_level: importance_level,
            percentile: percentile,
          };
        }

        return node;
      });

      console.log(
        `✅ Applied centrality visualization to ${updatedPositions.length} nodes`,
      );

      return {
        ...state,
        positions: updatedPositions,
        nodes: updatedNodes,
        centralityInfo: {
          type: centrality_type,
          calculationId: calculation_id,
          applied: true,
          timestamp: new Date().toISOString(),
        },
      };
    });
  },

  // Clear all data
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

  // Upload network file using GraphML-based API
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

        useChatStore
          .getState()
          .setCurrentConversationId(result.conversation_id);

        useChatStore.getState().addMessage({
          role: "assistant",
          content: `ファイル "${file.name}" が正常にアップロードされ、新しいネットワークが作成されました。`,
          timestamp: new Date().toISOString(),
        });

        const cytoscapeResponse = await networkAPI.getNetworkCytoscape(
          result.network_id,
        );
        const cytoData = cytoscapeResponse.data;

        if (cytoData && cytoData.elements) {
          set({
            nodes: cytoData.elements.nodes.map((n) => n.data),
            edges: cytoData.elements.edges.map((e) => e.data),
            positions: cytoData.elements.nodes.map((n) => ({
              ...n.data,
              ...n.position,
            })),
            isLoading: false,
            error: null,
          });
          return { success: true };
        } else {
          throw new Error(
            "Failed to retrieve valid Cytoscape data after upload.",
          );
        }
      } else {
        const errorMessage =
          result.detail || "Unknown error during file upload process.";
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

  // Export network as GraphML
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

  // Get network information
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
        const nodes = cytoData.elements.nodes.map((n) => n.data);
        const edges = cytoData.elements.edges.map((e) => e.data);
        const positions = cytoData.elements.nodes.map((n) => ({
          ...n.data,
          ...n.position,
        }));
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
