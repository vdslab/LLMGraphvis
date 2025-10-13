/**
 * WebSocket service for real-time communication with the API server.
 * Handles connection, reconnection, and message processing.
 */

import useNetworkStore from "./networkStore";
import { networkAPI } from "./api";

class WebSocketService {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimeout = null;
    this.reconnectInterval = 3000; // 3秒
    this.url = `ws://${window.location.hostname}:8000/ws`;
  }

  /**
   * Connect to the WebSocket server
   */
  connect() {
    // 既に接続されている場合は何もしない
    if (this.isConnected) {
      console.log("WebSocket already connected");
      return;
    }

    // トークンを取得
    const token = localStorage.getItem("token");
    if (!token) {
      console.error("No token found, cannot connect to WebSocket");
      return;
    }

    // WebSocketに接続
    try {
      this.socket = new WebSocket(`${this.url}?token=${token}`);

      // 接続イベントハンドラ
      this.socket.onopen = this.onOpen.bind(this);
      this.socket.onmessage = this.onMessage.bind(this);
      this.socket.onclose = this.onClose.bind(this);
      this.socket.onerror = this.onError.bind(this);
    } catch (error) {
      console.error("Error connecting to WebSocket:", error);
    }
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
      this.isConnected = false;
      console.log("WebSocket disconnected");
    }

    // 再接続タイマーをクリア
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  /**
   * Handle WebSocket open event
   */
  onOpen() {
    console.log("WebSocket connected");
    this.isConnected = true;
    this.reconnectAttempts = 0;
  }

  /**
   * Handle WebSocket message event
   * @param {MessageEvent} event - WebSocket message event
   */
  onMessage(event) {
    try {
      const data = JSON.parse(event.data);
      console.log("WebSocket message received:", data);

      // Validate message structure
      if (!data || typeof data !== "object") {
        console.warn("Invalid WebSocket message format:", event.data);
        return;
      }

      // イベントタイプに基づいて処理
      if (data.event === "graph_updated") {
        console.log("Graph update notification received:", data);
        this.handleGraphUpdated(data);
      } else if (data.event === "layout_updated") {
        console.log("Layout update notification received:", data);
        this.handleLayoutUpdate(data);
      } else {
        console.log("Unknown WebSocket event type:", data.event);
      }
    } catch (error) {
      console.error(
        "Error processing WebSocket message:",
        error,
        "Raw data:",
        event.data,
      );
    }
  }

  /**
   * Handle WebSocket close event
   */
  onClose() {
    console.log("WebSocket connection closed");
    this.isConnected = false;

    // 再接続を試みる
    this.attemptReconnect();
  }

  /**
   * Handle WebSocket error event
   * @param {Event} error - WebSocket error event
   */
  onError(error) {
    console.error("WebSocket error:", error);
    this.isConnected = false;
  }

  /**
   * Attempt to reconnect to the WebSocket server
   */
  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Maximum reconnect attempts reached");
      return;
    }

    this.reconnectAttempts++;
    console.log(
      `Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`,
    );

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, this.reconnectInterval);
  }

  /**
   * Handle graph updated event
   * @param {object} data - Event data
   */
  async handleGraphUpdated(data) {
    console.log("Graph updated event received:", data);

    // Validate input data
    if (!data || typeof data !== "object") {
      console.error("Invalid graph updated event data:", data);
      return;
    }

    // ネットワークIDを取得
    const networkId = data.network_id;
    if (!networkId) {
      console.error("No network ID in graph updated event:", data);
      return;
    }

    // Check if this is a layout update with direct position data
    if (
      data.network_update &&
      data.network_update.type === "change_layout" &&
      data.network_update.positions
    ) {
      console.log("Processing layout update from WebSocket with position data");
      try {
        this.handleLayoutUpdate(data.network_update);
      } catch (error) {
        console.error("Error handling layout update from WebSocket:", error);
      }
      return;
    }

    try {
      // 最新のネットワークデータを取得
      console.log(`Fetching updated network data for network ID: ${networkId}`);
      const response = await networkAPI.getNetworkCytoscape(networkId);

      if (!response || !response.data) {
        console.error("Invalid response from network API:", response);
        return;
      }

      const networkData = response.data;
      console.log("Received updated network data:", networkData);

      // ネットワークストアを更新 - Handle new API format
      if (networkData && networkData.elements) {
        // Handle both old format (array with nodes/edges mixed) and new format (object with nodes/edges properties)
        let nodes = [];
        let edges = [];

        if (Array.isArray(networkData.elements)) {
          // Old format: elements is an array
          nodes = networkData.elements.filter(
            (el) => el.data && !el.data.source,
          );
          edges = networkData.elements.filter(
            (el) => el.data && el.data.source,
          );
        } else if (networkData.elements.nodes && networkData.elements.edges) {
          // New format: elements is an object with nodes and edges arrays
          nodes = networkData.elements.nodes || [];
          edges = networkData.elements.edges || [];
        }

        console.log(
          `Updating network store with ${nodes.length} nodes and ${edges.length} edges`,
        );

        if (nodes.length > 0) {
          // ノードとエッジをネットワークストアに設定
          const mappedNodes = nodes.map((node) => ({
            id: node.data.id,
            label: node.data.label || node.data.name || node.data.id,
            ...node.data,
          }));

          const mappedEdges = edges.map((edge) => ({
            source: edge.data.source,
            target: edge.data.target,
            id: edge.data.id || `${edge.data.source}-${edge.data.target}`,
            ...edge.data,
          }));

          // Extract positions from node data
          const positions = nodes.map((node) => {
            const position = node.position || {};
            const data = node.data || {};
            return {
              id: data.id,
              label: data.label || data.name || data.id,
              x: parseFloat(position.x || data.x || 0),
              y: parseFloat(position.y || data.y || 0),
              size: parseFloat(data.size || 5),
              color: data.color || "#1d4ed8",
            };
          });

          const networkStore = useNetworkStore.getState();
          networkStore.setNetworkData(mappedNodes, mappedEdges);
          networkStore.setPositions(positions);

          console.log("Network data updated successfully via WebSocket");
        }
      } else {
        console.warn(
          "Network data is missing or has no elements:",
          networkData,
        );
      }
    } catch (error) {
      console.error("Error fetching updated network data:", error);
    }
  }

  /**
   * Handle layout update with position data
   * @param {object} networkUpdate - Network update data
   */
  handleLayoutUpdate(networkUpdate) {
    console.log(
      "Processing layout update with positions:",
      networkUpdate.positions,
    );

    try {
      const { positions: newPositionsData } = networkUpdate;
      const networkStore = useNetworkStore.getState();
      const currentPositions = networkStore.positions;

      if (currentPositions && currentPositions.length > 0) {
        // Update existing positions
        const updatedPositions = currentPositions.map((node) => {
          const newPos = newPositionsData[node.id];
          if (newPos) {
            return {
              ...node,
              x: parseFloat(newPos.x || 0),
              y: parseFloat(newPos.y || 0),
            };
          }
          return node;
        });

        networkStore.setPositions(updatedPositions);
        console.log(
          `Updated ${updatedPositions.length} node positions from WebSocket`,
        );
      } else {
        console.warn("No current positions to update");
      }
    } catch (error) {
      console.error("Error processing layout update:", error);
    }
  }
}

// シングルトンインスタンスを作成してエクスポート
const websocketService = new WebSocketService();
export default websocketService;
