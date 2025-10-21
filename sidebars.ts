import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    'introduction',
    'system-overview',
    'architecture-design',
    'component-details',
    'data-flow-example',
    'sequence-diagram',
    'roadmap',
    {
      type: 'category',
      label: 'Reference',
      items: [
        'reference/DeepResearch',
        'reference/仕様書',
      ],
    },
  ],
};

export default sidebars;