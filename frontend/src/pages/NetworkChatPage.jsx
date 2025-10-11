import { useState, useEffect, useRef } from "react";
import { settingsAPI } from "../services/api";
import CytoscapeGraph from "../components/CytoscapeGraph";
import { LayoutTypes, StylePresets } from "../constants/cytoscapePresets";
import useNetworkStore from "../services/networkStore";
import useChatStore from "../services/chatStore";
import ReactMarkdown from "react-markdown";
import { networkAPI } from "../services/api";
import FileUploadButton from "../components/FileUploadButton";

const NetworkChatPage = () => {
  const {
    nodes,
    edges,
    positions,
    isLoading,
    error,
    centralityInfo,
    uploadNetworkFile,
    // Unused functions removed
  } = useNetworkStore();

  // ネットワーク状態を保持
  const [network_state, setNetworkState] = useState({
    centrality: null,
    centralityDescription: null,
    isApplyingCentrality: false,
    currentCentralityName: "",
  });

  // ネットワーク情報を取得
  // ネットワーク情報を取得するuseEffectは削除し、初期化ロジックを一元化

  const { messages, sendMessage, isProcessing, addMessage } = useChatStore();

  const [inputMessage, setInputMessage] = useState("");
  // Mobile: control left chat panel visibility
  const [isChatOpenMobile, setIsChatOpenMobile] = useState(false);
  // LLM provider state
  // LLM provider/model state
  const [llmProvider, setLlmProvider] = useState("google");
  const [llmModel, setLlmModel] = useState("");
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState(null);

  // Model options for each provider
  const MODEL_OPTIONS = {
    google: [
      { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
      { value: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite" },
      { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
    ],
    openai: [
      { value: "gpt-3.5-turbo", label: "ChatGPT o3 mini" },
      { value: "gpt-4-turbo", label: "ChatGPT o4 mini" },
      { value: "gpt-5-mini", label: "ChatGPT 5 mini" },
      { value: "gpt-5", label: "ChatGPT 5" },
      { value: "gpt-4o", label: "ChatGPT 4o" },
    ],
  };
  // Fetch current LLM provider on mount
  useEffect(() => {
    const fetchLlmProvider = async () => {
      setLlmLoading(true);
      setLlmError(null);
      try {
        const res = await settingsAPI.getLLMProviderSettings();
        if (res.data && res.data.provider) {
          setLlmProvider(res.data.provider);
          if (res.data.openai_model) setLlmModel(res.data.openai_model);
          else if (res.data.provider === "google")
            setLlmModel("gemini-2.5-flash");
          else if (res.data.provider === "openai") setLlmModel("gpt-4o");
        }
      } catch {
        setLlmError("Failed to load LLM provider settings");
      } finally {
        setLlmLoading(false);
      }
    };
    fetchLlmProvider();
  }, []);

  // Handle LLM provider change
  const handleLlmProviderChange = async (e) => {
    const newProvider = e.target.value;
    setLlmLoading(true);
    setLlmError(null);
    try {
      // Default to first model for new provider
      const defaultModel = MODEL_OPTIONS[newProvider][0]?.value || "";

      // Build settings object based on provider
      const settings = { provider: newProvider };
      if (newProvider === "openai") {
        settings.openai_model = defaultModel;
      }

      await settingsAPI.updateLLMProviderSettings(settings);
      setLlmProvider(newProvider);
      setLlmModel(defaultModel);
    } catch {
      setLlmError("Failed to update LLM provider");
    } finally {
      setLlmLoading(false);
    }
  };

  // Handle LLM model change
  const handleLlmModelChange = async (e) => {
    const newModel = e.target.value;
    setLlmLoading(true);
    setLlmError(null);
    try {
      // Build settings object based on provider
      const settings = { provider: llmProvider };
      if (llmProvider === "openai") {
        settings.openai_model = newModel;
      }

      await settingsAPI.updateLLMProviderSettings(settings);
      setLlmModel(newModel);
    } catch {
      setLlmError("Failed to update LLM model");
    } finally {
      setLlmLoading(false);
    }
  };
  // const [graphData, setGraphData] = useState({ nodes: [], links: [] }); // No longer needed with Cytoscape
  const [fileUploadError, setFileUploadError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const graphRef = useRef();
  const messagesEndRef = useRef();

  // Helper function to get graph style based on current state
  const getGraphStyle = () => {
    const { layout } = useNetworkStore.getState();

    if (centralityInfo && centralityInfo.applied) {
      return StylePresets.CENTRALITY;
    }

    // Use SPRING_LAYOUT style when layout is spring for better readability
    if (layout === "spring") {
      return StylePresets.SPRING_LAYOUT;
    }

    return StylePresets.DEFAULT;
  };

  // Helper function to handle node clicks
  const handleNodeClick = (nodeData) => {
    console.log("Node clicked:", nodeData);

    // ノードの属性情報を収集
    let nodeInfo = `**ノード「${nodeData.label || nodeData.id}」の情報**\n\n`;

    // 中心性値がある場合は表示
    if (centralityInfo && centralityInfo.applied) {
      const centralityType = centralityInfo.type;
      const centralityKey = `${centralityType}_centrality`;
      const centralityValue = nodeData[centralityKey];

      if (centralityValue !== undefined) {
        nodeInfo += `${centralityType.charAt(0).toUpperCase() + centralityType.slice(1)} 中心性値: ${centralityValue.toFixed(3)}\n\n`;
      }
    }

    // ノードの他の属性を表示
    for (const [key, value] of Object.entries(nodeData)) {
      // 表示する必要のないキーをスキップ
      if (
        !["id", "label", "x", "y", "size", "color"].includes(key) &&
        !key.endsWith("_centrality")
      ) {
        nodeInfo += `${key}: ${value}\n`;
      }
    }

    // チャットにメッセージを追加
    addMessage({
      role: "assistant",
      content: nodeInfo,
      timestamp: new Date().toISOString(),
    });
  };

  // Get Cytoscape elements from store
  // Temporary: Create Cytoscape elements from basic network data
  const cytoscapeElements = [];

  // Add nodes
  nodes.forEach((node) => {
    const position = positions.find((p) => p.id === node.id);
    cytoscapeElements.push({
      group: "nodes",
      data: {
        id: node.id,
        label: node.label || node.id,
        ...node,
      },
      position: position ? { x: position.x, y: position.y } : undefined,
    });
  });

  // Add edges
  edges.forEach((edge) => {
    cytoscapeElements.push({
      group: "edges",
      data: {
        id: edge.id || `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        ...edge,
      },
    });
  });

  // Handle file upload
  const handleFileUpload = async (file) => {
    setFileUploadError(null);

    // Check if file is provided
    if (!file) {
      setFileUploadError("No file selected");
      return;
    }

    // Check file extension
    const fileExtension = file.name.split(".").pop().toLowerCase();
    const supportedFormats = [
      "graphml",
      "gexf",
      "gml",
      "json",
      "net",
      "edgelist",
      "adjlist",
    ];

    if (!supportedFormats.includes(fileExtension)) {
      setFileUploadError(
        `Unsupported file format: .${fileExtension}. Supported formats: ${supportedFormats.join(", ")}`,
      );
      return;
    }

    try {
      // Upload file - より堅牢なエラーハンドリング
      console.log(`Attempting to upload network file: ${file.name}`);

      // ファイルが空でないことを確認
      if (file.size === 0) {
        setFileUploadError("File is empty");
        return;
      }

      // アップロード処理
      const result = await uploadNetworkFile(file);

      // 結果の検証を強化
      if (result && result.success === true) {
        console.log("Network file uploaded and processed successfully");

        // Add a system message to the chat
        addMessage({
          role: "assistant",
          content: `Network file "${file.name}" uploaded and processed successfully.`,
          timestamp: new Date().toISOString(),
        });
      } else if (result && result.error) {
        // エラーメッセージが結果オブジェクトに含まれている場合
        console.error("Failed to process network file:", result.error);
        setFileUploadError(result.error);
      } else {
        // 一般的なエラーの場合
        console.error("Failed to process network file: Unknown error");
        setFileUploadError("Failed to process network file");
      }
    } catch (error) {
      console.error("Error uploading network file:", error);
      // より詳細なエラーメッセージを提供
      const errorMessage =
        error.response?.data?.detail ||
        error.message ||
        "Error uploading network file";
      setFileUploadError(errorMessage);

      // チャットにエラーメッセージを追加
      addMessage({
        role: "assistant",
        content: `ファイルのアップロード中にエラーが発生しました: ${errorMessage}`,
        timestamp: new Date().toISOString(),
        error: true,
      });
    }
  };

  // Handle file drop
  const handleFileDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);

    // Get the dropped file
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  // Handle drag events
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  // Load user's saved networks
  useEffect(() => {
    const loadUserNetworks = async () => {
      try {
        const userId = localStorage.getItem("userId");
        if (!userId) {
          console.log("No user ID found, skipping network list loading");
          return;
        }

        // APIサーバーを経由してユーザーのネットワークリストを取得
        const response = await networkAPI.useTool("list_user_networks", {
          user_id: userId,
        });
        const result = response.data.result;
        if (result.success) {
          console.log("Loaded user networks:", result.networks);
        } else {
          console.error("Failed to load user networks:", result.error);
        }
      } catch (error) {
        console.error("Error loading user networks:", error);
      }
    };

    loadUserNetworks();
  }, []);

  // 初期ネットワーク読み込み - コンポーネントマウント時に一度だけ実行
  useEffect(() => {
    console.log("NetworkChatPage: Initial network load effect triggered");
    console.log("Current state:", {
      nodesLength: nodes?.length || 0,
      edgesLength: edges?.length || 0,
      positionsLength: positions?.length || 0,
      isLoading,
    });

    // 既にネットワークデータが完全に読み込まれている場合はスキップ
    if (positions?.length > 0 && edges?.length > 0 && nodes?.length > 0) {
      console.log(
        "NetworkChatPage: Complete network data already exists, skipping initial load",
      );
      return;
    }

    // 直接サンプルネットワークを生成する関数
    const generateSampleNetwork = () => {
      console.log("NetworkChatPage: Generating sample network directly");

      // サンプルネットワークを直接生成
      const sampleNodes = [];
      const sampleEdges = [];
      const samplePositions = [];

      // 中心ノード
      sampleNodes.push({
        id: "0",
        label: "Center Node",
      });

      // 中心ノードの位置
      samplePositions.push({
        id: "0",
        label: "Center Node",
        x: 0,
        y: 0,
        size: 8,
        color: "#1d4ed8",
      });

      // 10個の衛星ノード
      for (let i = 1; i <= 10; i++) {
        sampleNodes.push({
          id: i.toString(),
          label: `Node ${i}`,
        });

        // 中心ノードとの接続
        sampleEdges.push({
          source: "0",
          target: i.toString(),
        });

        // 円形に配置
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

      // 状態を直接更新
      setNetworkState((prevState) => ({
        ...prevState,
        centrality: null,
      }));

      return { sampleNodes, sampleEdges, samplePositions };
    };

    const loadInitialNetwork = async () => {
      try {
        console.log("NetworkChatPage: Loading initial network data");
        // トークンの確認
        const token = localStorage.getItem("token");
        if (!token) {
          console.error(
            "NetworkChatPage: No token found, cannot load initial network",
          );
          return;
        }

        try {
          // networkAPI.getSampleNetworkは削除されたため、このブロックは実行されない
        } catch (mcpError) {
          console.error(
            "NetworkChatPage: Error loading sample network via MCP client:",
            mcpError,
          );
          console.log(
            "NetworkChatPage: Falling back to direct sample network generation",
          );
        }

        // MCPクライアントでの読み込みに失敗した場合、サンプルネットワークを直接生成
        console.log("NetworkChatPage: Generating sample network directly");
        const { sampleNodes, sampleEdges, samplePositions } =
          generateSampleNetwork();

        // 状態を直接更新 - 重要: 他の関数が呼び出されないようにするため、完全な状態を一度に設定
        useNetworkStore.setState({
          nodes: sampleNodes,
          edges: sampleEdges,
          positions: samplePositions,
          layout: "spring",
          isLoading: false,
          error: null,
          // 以下のフラグを追加して、他の関数が不必要に呼び出されないようにする
          initialLoadComplete: true,
        });

        console.log("NetworkChatPage: Sample network generated successfully:", {
          nodesLength: sampleNodes.length,
          edgesLength: sampleEdges.length,
          positionsLength: samplePositions.length,
        });

        // 更新後の状態を確認 - 直接storeから取得して確実に最新の状態を確認
        const currentState = useNetworkStore.getState();
        console.log("NetworkChatPage: State after sample network generation:", {
          nodesLength: currentState.nodes?.length || 0,
          edgesLength: currentState.edges?.length || 0,
          positionsLength: currentState.positions?.length || 0,
          isLoading: currentState.isLoading,
          initialLoadComplete: currentState.initialLoadComplete,
        });
      } catch (error) {
        console.error("NetworkChatPage: Error loading initial network:", error);

        // エラーが発生した場合でも、サンプルネットワークを生成して表示
        try {
          console.log(
            "NetworkChatPage: Attempting to generate fallback sample network after error",
          );
          const { sampleNodes, sampleEdges, samplePositions } =
            generateSampleNetwork();

          useNetworkStore.setState({
            nodes: sampleNodes,
            edges: sampleEdges,
            positions: samplePositions,
            layout: "spring",
            isLoading: false,
            error: null,
            initialLoadComplete: true,
          });

          console.log(
            "NetworkChatPage: Fallback sample network generated successfully",
          );
        } catch (fallbackError) {
          console.error(
            "NetworkChatPage: Failed to generate fallback sample network:",
            fallbackError,
          );
        }
      }
    };

    loadInitialNetwork();
  }, [nodes?.length, edges?.length, positions?.length, isLoading]); // 必要な依存関係を追加

  // Handle window resize for graph
  useEffect(() => {
    const handleResize = () => {
      if (graphRef.current) {
        const width = window.innerWidth * (window.innerWidth >= 768 ? 0.65 : 1);
        const height =
          window.innerHeight - (window.innerWidth >= 768 ? 100 : 200);
        graphRef.current.width(width);
        graphRef.current.height(height);
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // The useEffect hook for processing network updates is no longer needed here.
  // The logic is now handled inside chatStore.js, which directly updates networkStore.
  // This component will automatically re-render when networkStore's state (like positions) changes.

  // Handle message submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isProcessing) {
      return;
    }
    const messageToSend = inputMessage;
    setInputMessage("");
    await sendMessage(messageToSend);
  };

  return (
    // Lock the page height under the navbar (Navbar h-16 = 4rem) so only inner panes can scroll
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex-1 min-h-0 flex flex-col md:flex-row overflow-hidden">
        {/* Left side - Chat panel */}
        <div
          className={
            // Mobile: slide-in drawer; Desktop: static panel
            `z-30 md:z-auto ` +
            `fixed md:static top-16 bottom-0 md:inset-auto left-0 ` +
            `w-full sm:w-4/5 md:w-2/5 lg:w-1/3 ` +
            `transform transition-transform duration-200 ease-out ` +
            `${isChatOpenMobile ? "translate-x-0" : "-translate-x-full md:translate-x-0"} ` +
            `flex flex-col bg-white border-r border-gray-200 shadow md:shadow-none min-h-0`
          }
        >
          {/* LLM Selector */}
          <div className="px-4 py-3 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
            <div className="flex flex-col space-y-3 sm:space-y-0 sm:flex-row sm:items-center sm:space-x-4">
              {/* Provider Selection */}
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium text-gray-700 min-w-0 whitespace-nowrap">
                  Provider:
                </label>
                <select
                  className="text-sm px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white min-w-0 flex-1 sm:flex-none sm:w-auto"
                  value={llmProvider}
                  onChange={handleLlmProviderChange}
                  disabled={llmLoading}
                >
                  <option value="google">Google (Gemini)</option>
                  <option value="openai">OpenAI (ChatGPT)</option>
                </select>
              </div>

              {/* Model Selection */}
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium text-gray-700 min-w-0 whitespace-nowrap">
                  Model:
                </label>
                <select
                  className="text-sm px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white min-w-0 flex-1 sm:flex-none sm:w-auto"
                  value={llmModel}
                  onChange={handleLlmModelChange}
                  disabled={llmLoading}
                >
                  {(MODEL_OPTIONS[llmProvider] || []).map((model) => (
                    <option key={model.value} value={model.value}>
                      {model.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Status Indicators */}
              <div className="flex items-center space-x-2 flex-1 justify-end">
                {llmLoading && (
                  <div className="flex items-center space-x-2 text-blue-600">
                    <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                    <span className="text-sm font-medium">Switching...</span>
                  </div>
                )}
                {llmError && (
                  <div className="flex items-center space-x-1 text-red-600">
                    <svg
                      className="w-4 h-4"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="text-sm font-medium">{llmError}</span>
                  </div>
                )}
                {!llmLoading && !llmError && (
                  <div className="flex items-center space-x-1 text-green-600">
                    <svg
                      className="w-4 h-4"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="text-sm font-medium">Ready</span>
                  </div>
                )}
              </div>
            </div>

            {/* Rate Limit Info */}
            <div className="mt-2 text-xs text-gray-500">
              Using shared API keys with rate limiting (100 requests/hour)
            </div>
          </div>
          {/* Messages area */}
          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"} mb-4`}
              >
                {/* Avatar for assistant */}
                {message.role === "assistant" && (
                  <div className="flex-shrink-0 h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center mr-2">
                    <svg
                      className="h-5 w-5 text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 001.5 2.25m0 0v2.8a2.25 2.25 0 01-1.5 2.25m0 0a2.25 2.25 0 01-1.5 0M5 14.5v2.8a2.25 2.25 0 002.25 2.25h9A2.25 2.25 0 0018.5 17.3v-2.8a2.25 2.25 0 00-2.25-2.25h-.75m-6 0h6"
                      />
                    </svg>
                  </div>
                )}

                <div
                  className={`max-w-3/4 p-3 rounded-lg ${
                    message.role === "user"
                      ? "bg-blue-100 text-blue-900"
                      : "bg-gray-100 text-gray-900"
                  }`}
                >
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>

                  {/* Timestamp - would be added if messages had timestamps */}
                  {message.timestamp && (
                    <div className="text-xs text-gray-500 mt-1">
                      {new Date(message.timestamp).toLocaleTimeString()}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />

            {/* Typing indicator */}
            {isProcessing && (
              <div className="flex justify-start mb-4">
                <div className="flex-shrink-0 h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center mr-2">
                  <svg
                    className="h-5 w-5 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 001.5 2.25m0 0v2.8a2.25 2.25 0 01-1.5 2.25m0 0a2.25 2.25 0 01-1.5 0M5 14.5v2.8a2.25 2.25 0 002.25 2.25h9A2.25 2.25 0 0018.5 17.3v-2.8a2.25 2.25 0 00-2.25-2.25h-.75m-6 0h6"
                    />
                  </svg>
                </div>
                <div className="bg-gray-100 p-3 rounded-lg">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-100"></div>
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-200"></div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input area */}
          <div className="p-4 border-t border-gray-200 bg-white">
            <form onSubmit={handleSubmit} className="flex">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Type your message..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isProcessing}
              />
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                disabled={!inputMessage.trim() || isProcessing}
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              </button>
            </form>
            {fileUploadError && (
              <div className="mt-2 text-red-500 text-sm">{fileUploadError}</div>
            )}
          </div>
        </div>

        {/* Right side - Network visualization panel */}
        <div className="w-full md:flex-1 flex flex-col bg-white relative min-h-0">
          {/* Mobile toggle button to open chat panel */}
          <div className="md:hidden fixed bottom-4 left-4 z-30">
            <button
              type="button"
              aria-label="Open chat panel"
              onClick={() => setIsChatOpenMobile(true)}
              className="bg-white/90 backdrop-blur px-3 py-2 rounded-full shadow border border-gray-200 text-gray-700 flex items-center space-x-2"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="w-5 h-5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M7.5 8.25h9m-9 3h6m-6 3h9M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-sm font-medium">Chat</span>
            </button>
          </div>

          {/* Mobile: close button inside chat panel header overlay */}
          {isChatOpenMobile && (
            <button
              type="button"
              aria-label="Close chat panel"
              onClick={() => setIsChatOpenMobile(false)}
              className="md:hidden fixed top-[4.25rem] right-4 z-40 bg-white/90 backdrop-blur px-2.5 py-2 rounded-full shadow border border-gray-200"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="w-5 h-5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
          {/* Upload button - positioned for better visibility */}
          <div className="absolute top-4 right-4 z-20">
            <FileUploadButton
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg shadow-lg flex items-center justify-center transition-colors duration-200"
              buttonText="Upload Network File"
              onFileUpload={handleFileUpload}
            />
          </div>

          {/* Mobile upload button */}
          <div className="md:hidden fixed bottom-4 right-4 z-30">
            <FileUploadButton
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-3 rounded-full shadow-lg flex items-center justify-center transition-colors duration-200"
              buttonText="Upload"
              onFileUpload={handleFileUpload}
              iconOnly={true}
            />
          </div>

          {/* Graph visualization */}
          <div
            className={`flex-1 min-h-0 relative overflow-hidden ${isDragging ? "bg-blue-50" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleFileDrop}
          >
            {/* Drag and drop instruction */}
            <div className="absolute top-16 left-1/2 transform -translate-x-1/2 bg-white bg-opacity-90 px-4 py-2 rounded-full text-sm text-gray-600 shadow-md border border-gray-200 z-10">
              Drag & drop network file here
            </div>

            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75 z-10">
                <div className="flex flex-col items-center">
                  <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                  <p className="mt-2 text-blue-500 font-medium">Loading...</p>
                </div>
              </div>
            )}

            {/* 中心性適用時のアニメーション表示 */}
            {network_state.isApplyingCentrality && (
              <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-40 z-10">
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  <p className="mt-2 text-blue-600 font-semibold">
                    {network_state.currentCentralityName}を適用中...
                  </p>
                  <p className="text-sm text-blue-500">
                    ノードの大きさが中心性値に応じて変化します
                  </p>
                </div>
              </div>
            )}

            {error && (
              <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75 z-10">
                <div
                  className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative max-w-md mx-4"
                  role="alert"
                >
                  <strong className="font-bold">Error: </strong>
                  <span className="block sm:inline">{error}</span>
                </div>
              </div>
            )}

            {isDragging && (
              <div className="absolute inset-0 flex items-center justify-center bg-blue-50 bg-opacity-90 z-10 border-2 border-blue-500 border-dashed">
                <div className="text-blue-500 text-xl font-semibold">
                  Drop your network file here
                </div>
              </div>
            )}

            <div id="graph-area-wrap" className="w-full h-full min-h-[480px]">
              <CytoscapeGraph
                elements={cytoscapeElements}
                layout={LayoutTypes.PRESET}
                style={getGraphStyle()}
                className="w-full h-full"
                onNodeClick={handleNodeClick}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NetworkChatPage;
