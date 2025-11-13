import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebars: SidebarsConfig = {
  specsSidebar: [
    {
      type: "doc",
      id: "README",
      label: "はじめに",
    },
    {
      type: "category",
      label: "エグゼクティブサマリー",
      link: {
        type: "doc",
        id: "Executive_Summary/README",
      },
      items: [],
    },
    {
      type: "category",
      label: "クイックスタートガイド",
      link: {
        type: "doc",
        id: "Quick_Start/README",
      },
      items: [],
    },
    {
      type: "category",
      label: "詳細技術仕様",
      items: [
        {
          type: "doc",
          id: "Technical_Details/Architecture",
          label: "0. アーキテクチャ設計",
        },
        {
          type: "doc",
          id: "Technical_Details/Backend",
          label: "1. バックエンド仕様 (API)",
        },
        {
          type: "doc",
          id: "Technical_Details/Frontend",
          label: "2. フロントエンド仕様",
        },
        {
          type: "doc",
          id: "Technical_Details/NetworkXMCP",
          label: "3. ネットワーク計算サービス仕様",
        },
        {
          type: "doc",
          id: "Technical_Details/Database",
          label: "4. データベーススキーマ仕様",
        },
        {
          type: "doc",
          id: "Technical_Details/Authentication",
          label: "5. 認証フロー",
        },
        {
          type: "doc",
          id: "Technical_Details/Core_Workflows",
          label: "6. 主要な処理フローとデータ生成",
        },
        {
          type: "doc",
          id: "Technical_Details/Core_Workflows_Optimized",
          label: "6.1 主要な処理フロー（最適化版）",
        },
      ],
    },
    {
      type: "category",
      label: "開発者ガイド",
      items: ["Developer_Guide/developer_guide"],
    },
    {
      type: "category",
      label: "リファクタリング計画",
      items: [
        "Refactoring_Plan/refactoring_plan",
        "Refactoring_Plan/api_models_split",
        "Refactoring_Plan/api_network_module_split",
        "Refactoring_Plan/common_data_models",
        "Refactoring_Plan/common_exceptions",
        "Refactoring_Plan/common_graphml_utils",
        "Refactoring_Plan/common_logging",
        "Refactoring_Plan/error_handling_unification",
        "Refactoring_Plan/networkx_mcp_structure",
        "Refactoring_Plan/data_model_normalization",
      ],
    },
    {
      type: "category",
      label: "付録",
      items: [
        "Appendix/api_specification",
        "Appendix/networkx_mcp_specification",
        "Appendix/architecture_diagrams",
      ],
    },
  ],
};

export default sidebars;
