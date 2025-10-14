import { create } from "zustand";
import { networkAPI } from "./api";
import useChatStore from "./chatStore";

// Helper: coerce numeric-like values to numbers, leave other values untouched
const coerceNumber = (v) => {
  if (v === null || v === undefined) return v;
  // If already a number, return as-is
  if (typeof v === "number") return v;
  // Try numeric conversion from string/other
  const n = Number(v);
  return Number.isNaN(n) ? v : n;
};

// Centralized sample network generation
const generateSampleNetwork = () => {
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

  // 10 satellite nodes in circular arrangement
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

  return { sampleNodes, sampleEdges, samplePositions };
};

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
  initialLoadComplete: false,
  visualProperties: {
    node_size: 5,
    node_color: "#1d4ed8",
    edge_width: 1,
    edge_color: "#94a3b8",
  },

  // Initialize network with sample data if no data exists
  initializeNetwork: () => {
    const { nodes, positions, initialLoadComplete } = get();

    if (initialLoadComplete || (positions?.length > 0 && nodes?.length > 0)) {
      return true;
    }

    const { sampleNodes, sampleEdges, samplePositions } =
      generateSampleNetwork();

    set({
      nodes: sampleNodes,
      edges: sampleEdges,
      positions: samplePositions,
      layout: "spring",
      isLoading: false,
      error: null,
      initialLoadComplete: true,
    });

    return true;
  },

  // Load sample network using API (same as initializeNetwork but can force reload)
  loadSampleNetwork: async () => {
    console.log("Generating static sample network");
    set({ isLoading: true, error: null });

    try {
      const { sampleNodes, sampleEdges, samplePositions } =
        generateSampleNetwork();

      set({
        nodes: sampleNodes,
        edges: sampleEdges,
        positions: samplePositions,
        layout: "spring",
        isLoading: false,
        error: null,
        initialLoadComplete: true,
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

  // Direct centrality calculation using current frontend network
  calculateCentralityDirect: async (
    centralityType = "degree",
    colorScheme = "viridis",
    sizeRange = [10, 200], // Updated for better node visibility
  ) => {
    const { nodes, edges } = get();

    if (!nodes || !edges || nodes.length === 0) {
      set({ error: "No network data available for centrality calculation" });
      return false;
    }

    set({ isLoading: true, error: null });

    try {
      console.log(
        `🎯 Direct centrality calculation: ${centralityType} for ${nodes.length} nodes`,
      );

      const requestData = {
        network: {
          nodes: nodes,
          edges: edges,
        },
        centrality_type: centralityType,
        color_scheme: colorScheme,
        size_range: sizeRange,
      };

      const response = await networkAPI.calculateCentralityDirect(requestData);
      const result = response.data;

      if (result && result.success) {
        console.log("✅ Direct centrality calculation completed:", result);

        // Apply the visualization data directly
        const { visualization_data, centrality_type, calculation_id } = result;

        set((state) => {
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
                `🎨 Updating node ${nodeId}: size=${size}, color=${color}, centrality=${centrality_value}`,
              );

              return {
                ...node,
                color: color,
                size: size,
                [`${centrality_type}_centrality`]: centrality_value,
                centrality_value: centrality_value,
                importance_level: importance_level,
                percentile: percentile,
                originalColor: node.originalColor || node.color || "#1d4ed8",
                originalSize: node.originalSize || node.size || 5,
              };
            }
            return node;
          });

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
            `✅ Applied direct centrality visualization to ${updatedPositions.length} nodes`,
          );

          return {
            ...state,
            positions: updatedPositions,
            nodes: updatedNodes,
            isLoading: false,
            error: null,
            centralityInfo: {
              type: centrality_type,
              calculationId: calculation_id,
              applied: true,
              timestamp: new Date().toISOString(),
            },
          };
        });

        return true;
      } else {
        throw new Error(result.detail || "Centrality calculation failed");
      }
    } catch (error) {
      console.error("❌ Error in direct centrality calculation:", error);
      set({
        isLoading: false,
        error:
          error.response?.data?.detail ||
          error.message ||
          "Failed to calculate centrality",
      });
      return false;
    }
  },

  // Clear all data
  clearData: () => {
    set({
      nodes: [],
      edges: [],
      positions: [],
      centrality: null,
      centralityType: null,
      error: null,
      initialLoadComplete: false,
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

      // Accept either { network_id } or { id } as the returned network identifier
      const returnedNetworkId = result?.network_id || result?.id;
      const returnedConversationId = result?.conversation_id || null;

      if (result && returnedNetworkId && returnedConversationId) {
        console.log("File uploaded successfully. New data:", result);

        useChatStore
          .getState()
          .setCurrentConversationId(returnedConversationId);

        useChatStore.getState().addMessage({
          role: "assistant",
          content: `ファイル "${file.name}" が正常にアップロードされ、新しいネットワークが作成されました。`,
          timestamp: new Date().toISOString(),
        });

        const cytoscapeResponse =
          await networkAPI.getNetworkCytoscape(returnedNetworkId);
        const cytoData = cytoscapeResponse.data;

        if (cytoData && cytoData.elements) {
          // Defensive: some nodes may not include 'position' (no x/y), avoid spreading undefined
          const mappedNodes = cytoData.elements.nodes.map((n) => {
            const data = n.data || {};
            // Build a stable node object and coerce numeric-like values
            const id = data.id ?? n.data?.id ?? n.id ?? data.label;
            const x = coerceNumber(data.x ?? n.position?.x ?? n.x);
            const y = coerceNumber(data.y ?? n.position?.y ?? n.y);
            const size = coerceNumber(
              data.size ?? n.position?.size ?? data.node_size ?? undefined,
            );

            return {
              // preserve original data fields but prefer coerced numeric fields for x/y/size
              ...data,
              id,
              ...(x !== undefined ? { x } : {}),
              ...(y !== undefined ? { y } : {}),
              ...(size !== undefined ? { size } : {}),
            };
          });

          const mappedEdges = (cytoData.elements.edges || []).map((e) => {
            const d = e.data || {};
            return {
              ...d,
              width: coerceNumber(
                d.width ?? d.edge_width ?? d.weight ?? undefined,
              ),
              weight: coerceNumber(d.weight ?? d.edge_weight ?? undefined),
            };
          });

          const mappedPositions = cytoData.elements.nodes.map((n) => {
            const dataPart = n.data || {};
            const posPart = n.position || {};

            // Coerce numeric fields if present (GraphML may return strings)
            const x = coerceNumber(posPart.x ?? dataPart.x ?? undefined);
            const y = coerceNumber(posPart.y ?? dataPart.y ?? undefined);
            const size = coerceNumber(
              dataPart.size ?? posPart.size ?? undefined,
            );

            return {
              id: dataPart.id ?? n.id ?? dataPart.label,
              label: dataPart.label ?? dataPart.id,
              ...(x !== undefined ? { x } : {}),
              ...(y !== undefined ? { y } : {}),
              ...(size !== undefined ? { size } : {}),
              color: dataPart.color ?? dataPart.node_color ?? "#1d4ed8",
            };
          });
          console.log(
            "uploadNetworkFile: mappedNodes",
            mappedNodes.length,
            "mappedEdges",
            mappedEdges.length,
            "mappedPositions",
            mappedPositions.length,
          );

          set({
            nodes: mappedNodes,
            edges: mappedEdges,
            positions: mappedPositions,
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
        const nodes = cytoData.elements.nodes.map((n) => {
          const d = n.data || {};
          return {
            ...d,
            id: d.id ?? n.id ?? d.label,
            x: coerceNumber(d.x ?? n.position?.x ?? undefined),
            y: coerceNumber(d.y ?? n.position?.y ?? undefined),
            size: coerceNumber(d.size ?? n.position?.size ?? undefined),
          };
        });

        const edges = (cytoData.elements.edges || []).map((e) => {
          const d = e.data || {};
          return {
            ...d,
            width: coerceNumber(
              d.width ?? d.edge_width ?? d.weight ?? undefined,
            ),
            weight: coerceNumber(d.weight ?? d.edge_weight ?? undefined),
          };
        });

        const positions = cytoData.elements.nodes.map((n) => {
          const d = n.data || {};
          const p = n.position || {};
          return {
            id: d.id ?? n.id ?? d.label,
            label: d.label ?? d.id,
            x: coerceNumber(p.x ?? d.x ?? undefined),
            y: coerceNumber(p.y ?? d.y ?? undefined),
            size: coerceNumber(d.size ?? p.size ?? undefined),
            color: d.color ?? d.node_color ?? "#1d4ed8",
          };
        });
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
