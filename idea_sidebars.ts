import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    {
      type: 'category',
      label: 'Overview',
      items: ['index'],
    },    {
      type: 'category',
      label: 'Requirements',
      items: [
        'requirements/system-overview',
        'requirements/functional-requirements',
        'requirements/non-functional-requirements',
      ],
    },
    {
      type: 'category',
      label: 'System Design',
      items: [
        'system-design/architecture-design',
        'system-design/error-handling-design',
        'system-design/operations-design',
        'system-design/data-flow-example',
        'system-design/sequence-diagram',
        'system-design/upload-data-flow',
      ],
    },
    {
      type: 'category',
      label: 'Basic Design',
      items: [
        'basic-design/component-details',
        'basic-design/screen-design',
        'basic-design/api-specifications',
        'basic-design/database-schema',
        'basic-design/roadmap',
      ],
    },
    {
      type: 'category',
      label: 'Detailed Design',
      items: [
        'detailed-design/詳細設計',
      ],
    },
  ],
};

export default sidebars;