/**
 * ネットワークチャットページ
 * 
 * グラフ可視化とチャットインターフェースを統合した画面
 * 重要: このコンポーネントは純粋なレイアウト構造のみを定義し、
 * 子コンポーネントにロジックを委任しています。
 */
import { useState } from "react";
import ChatPanel from "../components/chat/ChatPanel";
import GraphPanel from "../components/graph/GraphPanel";

// ネットワーク分析とチャットを統合したメイン画面
const NetworkChatPage = () => {
  // 複雑なロジックは全て子コンポーネントに移動済み
  return (
    <div className="flex h-screen">
      {/* 左側: チャットパネル */}
      <ChatPanel />
      
      {/* 右側: グラフパネル */}
      <GraphPanel />
    </div>
  );
};

export default NetworkChatPage;