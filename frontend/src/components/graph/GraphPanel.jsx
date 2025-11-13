import { useState, useRef, useEffect } from "react";
import NetworkGraph from "./NetworkGraph";
import GraphControls from "./GraphControls";
import useNetworkStore from "../../services/networkStore";
import useChatStore from "../../services/chatStore";

/**
 * グラフ表示パネルコンポーネント
 * 
 * グラフの表示と操作機能を統合
 * - ファイルアップロード
 * - ドラッグ＆ドロップ
 * - グラフ描画
 * 
 * @returns {JSX.Element} グラフパネル
 */
const GraphPanel = () => {
  const {
    nodes,
    edges,
    positions,
    isLoading,
    error,
    uploadNetworkFile
  } = useNetworkStore();

  const { addMessage } = useChatStore();
  
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [fileUploadError, setFileUploadError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const graphContainerRef = useRef(null);
  const [graphDimensions, setGraphDimensions] = useState({ width: 0, height: 0 });

  // ネットワーク状態を保持
  const [networkState, setNetworkState] = useState({
    centrality: null,
    centralityDescription: null,
    isApplyingCentrality: false,
    currentCentralityName: ""
  });

  // ファイルアップロード処理
  const handleFileUpload = async (file) => {
    setFileUploadError(null);
    
    try {
      const result = await uploadNetworkFile(file);
      
      if (result && result.success === true) {
        // チャットにシステムメッセージを追加
        addMessage({
          role: "assistant",
          content: `ネットワークファイル "${file.name}" がアップロードされ、処理されました。`,
          timestamp: new Date().toISOString(),
        });
      } else if (result && result.error) {
        setFileUploadError(result.error);
      } else {
        setFileUploadError("ファイルの処理に失敗しました");
      }
    } catch (error) {
      const errorMessage = error.response?.data?.detail || error.message || "ファイルのアップロード中にエラーが発生しました";
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

  // ドラッグ&ドロップ処理
  const handleFileDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  // グラフサイズの監視
  useEffect(() => {
    const updateGraphDimensions = () => {
      if (graphContainerRef.current) {
        setGraphDimensions({
          width: graphContainerRef.current.offsetWidth,
          height: graphContainerRef.current.offsetHeight,
        });
      }
    };

    updateGraphDimensions();
    window.addEventListener('resize', updateGraphDimensions);
    
    return () => {
      window.removeEventListener('resize', updateGraphDimensions);
    };
  }, []);

  // ノードクリック時の処理
  const handleNodeClick = (node) => {
    // ノードの属性情報を収集
    let nodeInfo = `**ノード「${node.label || node.id}」の情報**\n\n`;
    
    // 中心性値がある場合は表示
    if (networkState.centrality) {
      const centralityValue = ((node.size - 5) / 10).toFixed(3);
      nodeInfo += `中心性値: ${centralityValue}\n\n`;
      
      const importance = node.size > 12 
        ? "非常に重要" 
        : node.size > 9 
          ? "比較的重要" 
          : node.size > 7 
            ? "平均的な重要度" 
            : "あまり重要でない";
      
      nodeInfo += `このノードは${importance}位置にあります。\n\n`;
    }
    
    // その他の属性情報を表示
    nodeInfo += "**属性情報:**\n";
    for (const [key, value] of Object.entries(node)) {
      if (!['id', 'label', 'x', 'y', 'size', 'color', '__indexColor', 'index', 'vx', 'vy', 'fx', 'fy'].includes(key)) {
        nodeInfo += `- ${key}: ${value}\n`;
      }
    }
    
    // 基本情報も表示
    nodeInfo += "\n**基本情報:**\n";
    nodeInfo += `- ID: ${node.id}\n`;
    nodeInfo += `- ラベル: ${node.label || node.id}\n`;
    nodeInfo += `- サイズ: ${node.size}\n`;
    nodeInfo += `- 色: ${node.color}\n`;
    nodeInfo += `- 位置: (${node.x.toFixed(2)}, ${node.y.toFixed(2)})\n`;
    
    addMessage({
      role: "assistant",
      content: nodeInfo,
      timestamp: new Date().toISOString(),
    });
  };

  // positions と edges から graphData を生成
  useEffect(() => {
    if (positions.length > 0) {
      const graphNodes = positions.map((node) => ({
        id: node.id,
        x: node.x * 100, // より良い視覚化のためにスケール
        y: node.y * 100,
        label: node.label || node.id,
        size: node.size || 5,
        color: node.color || "#1d4ed8",
      }));

      const graphLinks = edges.map((edge) => ({
        source: edge.source,
        target: edge.target,
        width: edge.width || 1,
        color: edge.color || "#94a3b8",
      }));

      setGraphData({ nodes: graphNodes, links: graphLinks });
    }
  }, [positions, edges]);

  return (
    <div className="flex-1 flex flex-col bg-white">
      {/* グラフ操作UI */}
      <GraphControls 
        onFileUpload={handleFileUpload}
        error={fileUploadError}
        isLoading={isLoading}
      />
      
      {/* グラフ描画エリア */}
      <div
        ref={graphContainerRef}
        className={`flex-1 relative ${isDragging ? "bg-blue-50" : ""} min-h-0`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleFileDrop}
      >
        {graphDimensions.width > 0 && graphDimensions.height > 0 && (
          <NetworkGraph
            graphData={graphData}
            dimensions={graphDimensions}
            onNodeClick={handleNodeClick}
            networkState={networkState}
          />
        )}
        
        {/* ローディングインジケーター */}
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75">
            <div className="animate-spin h-12 w-12 border-4 border-blue-500 rounded-full border-t-transparent"></div>
          </div>
        )}
        
        {/* エラーメッセージ */}
        {error && !fileUploadError && (
          <div className="absolute bottom-4 left-4 right-4 bg-red-100 text-red-800 p-3 rounded shadow-md">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphPanel;