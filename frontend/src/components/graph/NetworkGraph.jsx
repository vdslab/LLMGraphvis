import { useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";

/**
 * ネットワークグラフ描画コンポーネント
 * 
 * ForceGraph2Dを使用してグラフを描画
 * 
 * @param {Object} graphData - グラフデータ {nodes, links}
 * @param {Object} dimensions - グラフの描画サイズ {width, height}
 * @param {Function} onNodeClick - ノードクリック時のコールバック
 * @param {Object} networkState - ネットワーク状態 (中心性表示等)
 * @returns {JSX.Element} ネットワークグラフ
 */
const NetworkGraph = ({ graphData, dimensions, onNodeClick, networkState }) => {
  const graphRef = useRef();

  // グラフが空の場合の表示
  if (!graphData.nodes || graphData.nodes.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400">
        <p>ネットワークデータがありません。<br/>ファイルをアップロードするか、チャットで生成してください。</p>
      </div>
    );
  }
  
  return (
    <ForceGraph2D
      ref={graphRef}
      graphData={graphData}
      width={dimensions.width}
      height={dimensions.height}
      
      // 基本設定
      nodeLabel={(node) => {
        // ノードの基本情報を表示
        let label = `${node.label || node.id}`;
        
        // 中心性値がある場合は表示
        if (networkState.centrality) {
          label += `\n中心性値: ${node.size ? ((node.size - 5) / 10).toFixed(2) : "不明"}`;
        }
        
        // ノードの属性情報を表示
        for (const [key, value] of Object.entries(node)) {
          // 基本情報と内部プロパティはスキップ
          if (!['id', 'label', 'x', 'y', 'size', 'color', '__indexColor', 'index', 'vx', 'vy', 'fx', 'fy'].includes(key)) {
            label += `\n${key}: ${value}`;
          }
        }
        
        return label;
      }}
      nodeRelSize={6}
      nodeVal={(node) => node.size}
      nodeColor={(node) => node.color}
      linkWidth={(link) => link.width}
      linkColor={(link) => link.color}
      
      // 物理シミュレーション設定
      cooldownTicks={100}
      onEngineStop={() => console.log("Layout stabilized")}
      
      // イベントハンドラ
      onNodeClick={onNodeClick}
      
      // カスタムレンダリング
      nodeCanvasObject={(node, ctx) => {
        const size = node.size || 5;
        
        // ノードの描画
        ctx.beginPath();
        ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
        ctx.fillStyle = node.color || "#1d4ed8";
        ctx.fill();

        // 中心性が高いノードの発光効果
        if (networkState.centrality && node.size > 7) {
          const glowSize = size * 1.5;
          const glowOpacity = (node.size - 5) / 10; // 中心性の正規化値（0〜1）

          ctx.beginPath();
          ctx.arc(node.x, node.y, glowSize, 0, 2 * Math.PI);
          ctx.fillStyle = `rgba(66, 153, 225, ${glowOpacity * 0.4})`; // 青色の発光効果
          ctx.fill();
        }
      }}
    />
  );
};

export default NetworkGraph;