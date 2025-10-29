import { themes as prismThemes } from "prism-react-renderer";
import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";
import "dotenv/config";

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: "GraphVisAgent Specification",
  tagline: "Graph Visualization Agent Specification",
  favicon: "img/favicon.ico",

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: "https://your-docusaurus-site.example.com",
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: "/",

  themes: ["@docusaurus/theme-mermaid"],
  markdown: {
    mermaid: true,
  },

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: "shirashoji", // Usually your GitHub org/user name.
  projectName: "GraphVisAgent", // Usually your repo name.

  onBrokenLinks: "ignore",

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      {
        docs: false, // Disable the default docs plugin
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],

  plugins: [

    // Existing plugin for specification
    [
      "@docusaurus/plugin-content-docs",
      {
        id: "specification",
        path: "specification",
        routeBasePath: "/specification/",
        sidebarPath: require.resolve("./sidebars-specs.ts"),

        editUrl: "https://github.com/shirashoji/GraphVisAgent/tree/main/",
      },
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: "img/docusaurus-social-card.jpg",
    colorMode: {
      respectPrefersColorScheme: true,
    },
    ...(process.env.ALGOLIA_APP_ID
      ? {
          algolia: {
            appId: process.env.ALGOLIA_APP_ID,
            apiKey: process.env.ALGOLIA_API_KEY!,
            indexName: process.env.ALGOLIA_INDEX_NAME!,
            contextualSearch: true,
          },
        }
      : {}),
    navbar: {
      title: "GraphVisAgent Specification",
      logo: {
        alt: "GraphVisAgent Logo",
        src: "img/logo.svg",
      },
      items: [
        {
          to: "/specification/",
          label: "Specification",
          position: "left",
        },
        {
          type: "docsVersionDropdown",
          docsPluginId: "specification",
          position: "right",
          to: "/",
        },

        {
          href: "https://github.com/shirashoji/GraphVisAgent",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Docs",
          items: [
            {
              label: "Specification",
              to: "/specification/",
            },
          ],
        },
        {
          title: "Community",
          items: [
            {
              label: "Stack Overflow",
              href: "https://stackoverflow.com/questions/tagged/docusaurus",
            },
            {
              label: "Discord",
              href: "https://discordapp.com/invite/docusaurus",
            },
            {
              label: "X",
              href: "https://x.com/docusaurus",
            },
          ],
        },
        {
          title: "More",
          items: [
            {
              label: "GitHub",
              href: "https://github.com/shirashoji/GraphVisAgent",
            },
          ],
        },
      ],
      copyright:
        "Copyright © 2024-2025 SHIRASHOJI Takuma. Built with Docusaurus.",
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
