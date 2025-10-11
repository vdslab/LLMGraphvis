import React, { useEffect, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import { LayoutTypes, StylePresets } from "../constants/cytoscapePresets";

const CytoscapeGraph = ({
  elements = [],
  layout = { name: "cose" },
  // 'style' prop here represents Cytoscape stylesheet (array). Keep name for backwards compatibility.
  style = [],
  className = "w-full h-full",
  onNodeClick = null,
  onEdgeClick = null,
  onLayoutReady = null,
  minZoom = 0.1,
  maxZoom = 5,
}) => {
  const cyRef = useRef(null);
  const [cyInstance, setCyInstance] = useState(null);

  // Default Cytoscape styles
  const defaultStyle = [
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
    {
      selector: "node:selected",
      style: {
        "background-color": "#e74c3c",
        "border-width": 3,
        "border-color": "#c0392b",
      },
    },
    {
      selector: "edge:selected",
      style: {
        "line-color": "#e74c3c",
        "target-arrow-color": "#e74c3c",
        width: 4,
      },
    },
  ];

  // Merge default Cytoscape stylesheet with provided style preset
  const mergedStylesheet =
    Array.isArray(style) && style.length > 0 ? style : defaultStyle;
  // Container CSS style (must be an object with width/height)
  const containerStyle = { width: "100%", height: "100%" };

  // Set up event handlers when Cytoscape instance is ready
  useEffect(() => {
    if (cyInstance) {
      // Node click handler
      if (onNodeClick) {
        cyInstance.on("tap", "node", (event) => {
          const node = event.target;
          onNodeClick(node.data(), event);
        });
      }

      // Edge click handler
      if (onEdgeClick) {
        cyInstance.on("tap", "edge", (event) => {
          const edge = event.target;
          onEdgeClick(edge.data(), event);
        });
      }

      // Layout ready handler
      if (onLayoutReady) {
        cyInstance.on("layoutready", (event) => {
          onLayoutReady(event);
        });
      }

      // Set zoom limits
      cyInstance.minZoom(minZoom);
      cyInstance.maxZoom(maxZoom);

      // Note: react-cytoscapejs/cytoscape doesn't expose a wheelSensitivity setter in all versions
    }

    // Cleanup event listeners
    return () => {
      if (cyInstance) {
        cyInstance.removeAllListeners();
      }
    };
  }, [cyInstance, onNodeClick, onEdgeClick, onLayoutReady, minZoom, maxZoom]);

  // Fit graph to container when elements change
  useEffect(() => {
    if (cyInstance && elements.length > 0) {
      setTimeout(() => {
        cyInstance.fit();
        cyInstance.center();
      }, 100);
    }
  }, [elements, cyInstance]);

  const handleCyReady = (cy) => {
    cyRef.current = cy;
    setCyInstance(cy);
  };

  // Render the Cytoscape component
  return (
    <div className={className}>
      <CytoscapeComponent
        elements={elements}
        layout={layout}
        // style is the container style for react-cytoscapejs
        style={containerStyle}
        // stylesheet is the Cytoscape styling definition
        stylesheet={mergedStylesheet}
        cy={handleCyReady}
        className="w-full h-full"
      />
    </div>
  );
};

export default CytoscapeGraph;
