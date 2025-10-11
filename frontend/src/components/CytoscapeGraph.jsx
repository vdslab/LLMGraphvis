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

  // Default Cytoscape styles with improved readability
  const defaultStyle = [
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

  // Fit graph to container when elements change with improved positioning
  useEffect(() => {
    if (cyInstance && elements.length > 0) {
      setTimeout(() => {
        // Fit the graph with padding for better visibility
        cyInstance.fit(undefined, 50); // 50px padding
        cyInstance.center();

        // Set a reasonable initial zoom level for spring layouts
        const currentZoom = cyInstance.zoom();
        if (currentZoom > 2) {
          cyInstance.zoom(2);
          cyInstance.center();
        } else if (currentZoom < 0.5) {
          cyInstance.zoom(0.5);
          cyInstance.center();
        }
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
