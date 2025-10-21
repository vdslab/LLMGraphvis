import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    {
      type: 'doc',
      id: 'introduction',
      label: 'はじめに',
    },
    {
      type: 'doc',
      id: 'system-overview',
      label: 'システム概要',
    },
    {
      type: 'doc',
      id: 'architecture-design',
      label: 'アーキテクチャ設計',
    },
    {
      type: 'doc',
      id: 'component-details',
      label: 'コンポーネント詳細',
    },
    {
      type: 'doc',
      id: 'data-flow-example',
      label: 'データフローの具体例',
    },
    {
      type: 'doc',
      id: 'sequence-diagram',
      label: 'プロンプト入力から画面更新まで',
    },
    {
      type: 'doc',
      id: 'upload-data-flow',
      label: 'グラフデータアップロードフロー',
    },
    {
      type: 'doc',
      id: 'roadmap',
      label: '実装ロードマップ',
    },
    {
      type: 'category',
      label: '参照',
      items: [
        {
          type: 'doc',
          id: 'reference/DeepResearch',
          label: '詳細調査',
        },
        {
          type: 'doc',
          id: 'reference/仕様書',
          label: '旧仕様書',
        },
      ],
    },
  ],
};

export default sidebars;