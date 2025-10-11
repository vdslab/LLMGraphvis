// Layout presets for Cytoscape.js graphs
export const LayoutTypes = {
  COSE: { name: "cose", animate: true, animationDuration: 1000 },
  CIRCLE: { name: "circle", animate: true, animationDuration: 1000 },
  GRID: { name: "grid", animate: true, animationDuration: 1000 },
  BREADTHFIRST: {
    name: "breadthfirst",
    animate: true,
    animationDuration: 1000,
  },
  CONCENTRIC: { name: "concentric", animate: true, animationDuration: 1000 },
  PRESET: { name: "preset" }, // For when positions are pre-calculated
  RANDOM: { name: "random", animate: true, animationDuration: 1000 },
};

// Style presets for different visualization types
export const StylePresets = {
  DEFAULT: [
    {
      selector: "node",
      style: {
        "background-color": "#1d4ed8",
        label: "data(label)",
        "text-valign": "center",
        "text-halign": "center",
        color: "white",
        "text-outline-width": 2,
        "text-outline-color": "#1d4ed8",
        "font-size": "14px",
        "font-weight": "bold",
        width: "mapData(size, 0, 10, 20, 60)",
        height: "mapData(size, 0, 10, 20, 60)",
        "border-width": 2,
        "border-color": "#1e40af",
        "border-opacity": 0.8,
        "background-opacity": 0.9,
      },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": "#94a3b8",
        "target-arrow-color": "#94a3b8",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        opacity: 0.7,
      },
    },
    {
      selector: "node:selected",
      style: {
        "background-color": "#dc2626",
        "border-color": "#b91c1c",
        "border-width": 4,
        "text-outline-color": "#dc2626",
      },
    },
    {
      selector: "edge:selected",
      style: {
        "line-color": "#dc2626",
        "target-arrow-color": "#dc2626",
        width: 4,
        opacity: 1,
      },
    },
  ],
  SPRING_LAYOUT: [
    {
      selector: "node",
      style: {
        "background-color": "#1d4ed8",
        label: "data(label)",
        "text-valign": "center",
        "text-halign": "center",
        color: "white",
        "text-outline-width": 2,
        "text-outline-color": "#1d4ed8",
        "font-size": "14px",
        "font-weight": "bold",
        width: "mapData(size, 0, 10, 25, 50)",
        height: "mapData(size, 0, 10, 25, 50)",
        "border-width": 2,
        "border-color": "#1e40af",
        "border-opacity": 0.8,
        "background-opacity": 0.9,
        "text-wrap": "wrap",
        "text-max-width": "80px",
      },
    },
    {
      selector: "edge",
      style: {
        width: "mapData(weight, 0, 5, 1, 4)",
        "line-color": "#94a3b8",
        "target-arrow-color": "#94a3b8",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        opacity: 0.6,
        "arrow-scale": 1.2,
      },
    },
    {
      selector: "node:selected",
      style: {
        "background-color": "#dc2626",
        "border-color": "#b91c1c",
        "border-width": 4,
        "text-outline-color": "#dc2626",
        "overlay-padding": "10px",
        "overlay-color": "#dc2626",
        "overlay-opacity": 0.2,
      },
    },
    {
      selector: "edge:selected",
      style: {
        "line-color": "#dc2626",
        "target-arrow-color": "#dc2626",
        width: 5,
        opacity: 1,
      },
    },
    {
      selector: "node:hover",
      style: {
        "background-color": "#3b82f6",
        "border-color": "#2563eb",
        "border-width": 3,
      },
    },
    {
      selector: "edge:hover",
      style: {
        "line-color": "#3b82f6",
        "target-arrow-color": "#3b82f6",
        width: 3,
        opacity: 0.8,
      },
    },
  ],
  CENTRALITY: [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        width: "data(size)",
        height: "data(size)",
        label: "data(label)",
        "text-valign": "center",
        "text-halign": "center",
        color: "white",
        "text-outline-width": 2,
        "text-outline-color": "black",
        "font-size": "12px",
        "font-weight": "bold",
        "border-width": 2,
        "border-color": "#000",
        "border-opacity": 0.3,
      },
    },
    {
      selector: "edge",
      style: {
        width: 1,
        "line-color": "#999",
        "curve-style": "bezier",
        opacity: 0.6,
      },
    },
  ],
  HIERARCHICAL: [
    {
      selector: "node",
      style: {
        "background-color": "#4CAF50",
        label: "data(label)",
        "text-valign": "center",
        "text-halign": "center",
        color: "white",
        "text-outline-width": 1,
        "text-outline-color": "#2E7D32",
        "font-size": "12px",
        "font-weight": "bold",
        width: 35,
        height: 35,
        "border-width": 2,
        "border-color": "#2E7D32",
      },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": "#757575",
        "target-arrow-color": "#757575",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
      },
    },
  ],
};
