import type {LoadContext, Plugin} from '@docusaurus/types';

export default function designDocsPlugin(context: LoadContext): Plugin {
  return {
    name: 'design-docs-plugin',
    async contentLoaded({actions}) {
      const {addRoute, createData} = actions;

      // Add a route for the design docs
      addRoute({
        path: '/design-docs',
        component: '@site/src/components/DesignDocsPage', // You might need to create this component
        exact: false, // Allow sub-routes
      });
    },
  };
}
