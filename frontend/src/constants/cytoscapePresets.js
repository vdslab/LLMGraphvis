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
        "background-color": "#666",
        label: "data(label)",
        "text-valign": "center",
        "text-halign": "center",
        color: "white",
        "text-outline-width": 2,
        "text-outline-color": "#666",
        "font-size": "12px",
        width: 30,
        height: 30,
      },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": "#ccc",
        "target-arrow-color": "#ccc",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
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
        "font-size": "10px",
      },
    },
    {
      selector: "edge",
      style: {
        width: 1,
        "line-color": "#999",
        "curve-style": "bezier",
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
        "font-size": "11px",
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
