import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'GraphVisAgent Specification',
  tagline: 'Graph Visualization Agent Specification',
  favicon: 'img/favicon.ico',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://your-docusaurus-site.example.com',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  themes: ['@docusaurus/theme-mermaid'],
  markdown: {
    mermaid: true,
  },

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'vdslab', // Usually your GitHub org/user name.
  projectName: 'GraphVisAgent', // Usually your repo name.

  onBrokenLinks: 'ignore',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: false, // Disable the default docs plugin
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  plugins: [
    [
      '@docusaurus/plugin-client-redirects',
      {
        redirects: [
          { from: '/', to: '/specification/' },
        ],
      },
    ],
    // New plugin for design_docs
    [
      '@docusaurus/plugin-content-docs',
      {
        id: 'design-docs',
        path: 'design_docs',
        routeBasePath: 'design-docs',
        sidebarPath: require.resolve('./idea_sidebars.ts'),
        editUrl: 'https://github.com/vdslab/GraphVisAgent/tree/main/',
      },
    ],
    // Existing plugin for specification
    [
      '@docusaurus/plugin-content-docs',
      {
        id: 'specification',
        path: 'specification',
        routeBasePath: '/specification/',
        sidebarPath: require.resolve('./sidebars-specs.ts'),

        editUrl: 'https://github.com/vdslab/GraphVisAgent/tree/main/',
      },
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'GraphVisAgent Specification',
      logo: {
        alt: 'GraphVisAgent Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          to: '/specification/',
          label: 'Specification',
          position: 'left',
        },
        {
          type: 'docsVersionDropdown',
          docsPluginId: 'specification',
          position: 'right',
          to: '/',
        },


        {
          href: 'https://github.com/vdslab/GraphVisAgent',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Design Docs',
              to: '/design-docs',
            },
            {
              label: 'Specification',
              to: '/',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'Stack Overflow',
              href: 'https://stackoverflow.com/questions/tagged/docusaurus',
            },
            {
              label: 'Discord',
              href: 'https://discordapp.com/invite/docusaurus',
            },
            {
              label: 'X',
              href: 'https://x.com/docusaurus',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/vdslab/GraphVisAgent',
            },
          ],
        },
      ],
      copyright: 'Copyright © 2024-2025 SHIRASHOJI Takuma. Built with Docusaurus.',
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;