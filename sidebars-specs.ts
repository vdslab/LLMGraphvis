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
      type: "category",
      label: "3. 主要な処理フロー",
      items: [
        {
          type: "doc",
          id: "Interactions",
          label: "3.1. 主要シーケンス",
        },
        {
          type: "doc",
          id: "rendering-data-flow",
          label: "3.2. 描画データ生成フロー",
        },
      ],
    },
    {
      type: "category",
      label: "4. 詳細設計・調査 (DeepResearch)",
      items: [
        {
          type: "doc",
          id: "DeepResearch/database",
          label: "4.1. データベース設計指針",
        },
        {
          type: "doc",
          id: "DeepResearch/degree-centrality-format",
          label: "4.2. 次数中心性フォーマット例",
        },
      ],
    },
  ],
};

export default sidebars;