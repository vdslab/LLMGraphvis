/**
 * WebSocket service for real-time communication with the API server.
 * Handles connection, reconnection, and message processing.
 */

import useNetworkStore from './networkStore';
import { networkAPI } from './api';

/**
 * WebSocket service for real-time communication.
 */
class WebSocketService {
  /**
   * Creates an instance of WebSocketService.
   */
  constructor() {
    /** @type {WebSocket|null} The WebSocket instance. */
    this.socket = null;
    /** @type {boolean} Whether the WebSocket is connected. */
    this.isConnected = false;
    /** @type {number} The number of reconnection attempts. */
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimeout = null;
    this.reconnectInterval = 3000; // 3秒
    this.url = `ws://${window.location.hostname}:8000/ws`;
  }

  /**
   * Connects to the WebSocket server.
   */
  connect() {
    // 既に接続されている場合は何もしない
    if (this.isConnected) {
      console.log('WebSocket already connected');
      return;
    }

    // トークンを取得
    const token = localStorage.getItem('token');
    if (!token) {
      console.error('No token found, cannot connect to WebSocket');
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
      console.error('Error connecting to WebSocket:', error);
    }
  }

  /**
   * Disconnects from the WebSocket server.
   */
  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
      this.isConnected = false;
      console.log('WebSocket disconnected');
    }

    // 再接続タイマーをクリア
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  /**
   * Handles the WebSocket open event.
   */
  onOpen() {
    console.log('WebSocket connected');
    this.isConnected = true;
    this.reconnectAttempts = 0;
  }

  /**
   * Handles incoming WebSocket messages.
   *
   * @param {MessageEvent} event - The WebSocket message event.
   */
  onMessage(event) {
    try {
      const data = JSON.parse(event.data);
      console.log('WebSocket message received:', data);

      // イベントタイプに基づいて処理
      if (data.event === 'graph_updated') {
        console.log('Graph update notification received:', data);
        this.handleGraphUpdated(data);
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }

  /**
   * Handles the WebSocket close event.
   */
  onClose() {
    console.log('WebSocket connection closed');
    this.isConnected = false;

    // 再接続を試みる
    this.attemptReconnect();
  }

  /**
   * Handles WebSocket errors.
   *
   * @param {Event} error - The WebSocket error event.
   */
  onError(error) {
    console.error('WebSocket error:', error);
    this.isConnected = false;
  }

  /**
   * Attempts to reconnect to the WebSocket server.
   */
  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Maximum reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, this.reconnectInterval);
  }

  /**
   * Handles the `graph_updated` event from the WebSocket.
   *
   * @param {object} data - The event data.
   */
  async handleGraphUpdated(data) {
    console.log('Graph updated event received:', data);

    // ネットワークIDを取得
    const networkId = data.network_id;
    if (!networkId) {
      console.error('No network ID in graph updated event');
      return;
    }

    try {
      // 最新のネットワークデータを取得
      console.log(`Fetching updated network data for network ID: ${networkId}`);
      const response = await networkAPI.getNetworkCytoscape(networkId);
      const networkData = response.data;
      console.log('Received updated network data:', networkData);

      // ネットワークストアを更新
      if (networkData && networkData.elements) {
        const nodes = networkData.elements.filter(el => el.data && !el.data.source);
        const edges = networkData.elements.filter(el => el.data && el.data.source);
        
        console.log(`Updating network store with ${nodes.length} nodes and ${edges.length} edges`);

        // ノードとエッジをネットワークストアに設定
        useNetworkStore.getState().setNetworkData(
          nodes.map(node => ({
            id: node.data.id,
            label: node.data.label || node.data.id,
            ...node.data
          })),
          edges.map(edge => ({
            source: edge.data.source,
            target: edge.data.target,
            ...edge.data
          }))
        );

        // レイアウトを再計算
        console.log('Recalculating layout for updated network');
        useNetworkStore.getState().calculateLayout();
      } else {
        console.warn('Network data is missing or has no elements:', networkData);
      }
    } catch (error) {
      console.error('Error fetching updated network data:', error);
    }
  }
}

// シングルトンインスタンスを作成してエクスポート
const websocketService = new WebSocketService();
export default websocketService;