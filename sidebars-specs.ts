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
        id: "0_Executive_Summary/README",
      },
      items: [],
    },
    {
      type: "category",
      label: "クイックスタートガイド",
      link: {
        type: "doc",
        id: "1_Quick_Start/README",
      },
      items: [],
    },
    {
      type: "category",
      label: "詳細技術仕様",
      items: [
        {
          type: "doc",
          id: "2_Technical_Details/0_Architecture",
          label: "0. アーキテクチャ設計",
        },
        {
          type: "doc",
          id: "2_Technical_Details/1_Backend",
          label: "1. バックエンド仕様 (API)",
        },
        {
          type: "doc",
          id: "2_Technical_Details/2_Frontend",
          label: "2. フロントエンド仕様",
        },
        {
          type: "doc",
          id: "2_Technical_Details/3_NetworkXMCP",
          label: "3. ネットワーク計算サービス仕様",
        },
        {
          type: "doc",
          id: "2_Technical_Details/4_Database",
          label: "4. データベーススキーマ仕様",
        },
        {
          type: "doc",
          id: "2_Technical_Details/5_Authentication",
          label: "5. 認証フロー",
        },
        {
          type: "doc",
          id: "2_Technical_Details/6_Core_Workflows",
          label: "6. 主要な処理フローとデータ生成",
        },
        {
          type: "doc",
          id: "2_Technical_Details/6_Core_Workflows_Optimized",
          label: "6.1 主要な処理フロー（最適化版）",
        },
      ],
    },
    {
      type: "category",
      label: "開発者ガイド",
      items: ["3_Developer_Guide/developer_guide"],
    },
    {
      type: "category",
      label: "リファクタリング計画",
      items: [
        "4_Refactoring_Plan/refactoring_plan",
        "4_Refactoring_Plan/api_models_split",
        "4_Refactoring_Plan/api_network_module_split",
        "4_Refactoring_Plan/common_data_models",
        "4_Refactoring_Plan/common_exceptions",
        "4_Refactoring_Plan/common_graphml_utils",
        "4_Refactoring_Plan/common_logging",
        "4_Refactoring_Plan/error_handling_unification",
        "4_Refactoring_Plan/networkx_mcp_structure",
      ],
    },
    {
      type: "category",
      label: "付録",
      items: [
        "5_Appendix/api_specification",
        "5_Appendix/networkx_mcp_specification",
        "5_Appendix/architecture_diagrams",
      ],
    },
  ],
};

export default sidebars;
