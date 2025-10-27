import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

/**
 * Creating a sidebar enables you to:
 *  - create an ordered group of docs
 *  - render a sidebar for each doc of that group
 *  - provide next/previous navigation
 *
 * The sidebars can be generated from the filesystem, or explicitly defined here.
 *
 * Create as many sidebars as you want.
 */
const sidebars: SidebarsConfig = {
  specsSidebar: [
    {
      type: "doc",
      id: "README",
      label: "はじめに",
    },
    {
      type: "doc",
      id: "Architecture",
      label: "1. アーキテクチャ設計",
    },
    {
      type: "category",
      label: "2. コンポーネント仕様",
      items: [
        {
          type: "doc",
          id: "Backend",
          label: "2.1. バックエンド (API)",
        },
        {
          type: "doc",
          id: "Frontend",
          label: "2.2. フロントエンド仕様",
        },
        {
          type: "doc",
          id: "NetworkXMCP",
          label: "2.3. グラフ計算サービス仕様 (NetworkXMCP)",
        },
      ],
    },
    {
      type: "doc",
      id: "Interactions",
      label: "3. 主要な処理フロー",
    },
    {
      type: "doc",
      id: "rendering-data-flow",
      label: "描画データ生成フロー",
    },
    {
      type: "category",
      label: "DeepResearch",
      items: [
        {
          type: "doc",
          id: "DeepResearch/database",
          label: "NetworkX 計算結果の永続化（DB 指針）",
        },
        {
          type: "doc",
          id: "DeepResearch/degree-centrality-format",
          label: "Degree 中心性の格納フォーマット",
        },
      ],
    },
  ],
};

export default sidebars;
