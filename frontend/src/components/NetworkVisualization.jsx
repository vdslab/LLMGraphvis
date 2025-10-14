import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import cytoscape from "cytoscape";
import klay from "cytoscape-klay";
import { layoutAPI } from "../services/api";

// Register the layout extension
cytoscape.use(klay);

const NetworkVisualization = ({ graph, onGraphUpdate, isLoading }) => {
  const cyContainerRef = useRef(null);
  const cyRef = useRef(null);
  const [selectedLayout, setSelectedLayout] = useState("klay");
  const [layoutLoading, setLayoutLoading] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [fitOnUpdate, setFitOnUpdate] = useState(true);

  // Layout options - memoized to avoid dependency issues
  const layoutOptions = useMemo(
    () => ({
      klay: {
        name: "klay",
        nodeDimensionsIncludeLabels: true,
        fit: true,
        padding: 20,
        klay: {
          spacing: 20,
          direction: "DOWN",
          thoroughness: 7,
        },
      },
      cose: {
        name: "cose",
        fit: true,
        padding: 20,
        nodeRepulsion: 400000,
        nodeOverlap: 10,
        idealEdgeLength: 100,
        edgeElasticity: 100,
        nestingFactor: 5,
        gravity: 80,
        numIter: 1000,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 1.0,
      },
      breadthfirst: {
        name: "breadthfirst",
        fit: true,
        padding: 20,
        directed: true,
        roots: "#a",
        spacingFactor: 1.75,
      },
      circle: {
        name: "circle",
        fit: true,
        padding: 20,
        radius: 200,
        spacingFactor: 1.5,
      },
      concentric: {
        name: "concentric",
        fit: true,
        padding: 20,
        startAngle: 3.14159 / 4,
        clockwise: true,
        equidistant: false,
        minNodeSpacing: 10,
      },
      grid: {
        name: "grid",
        fit: true,
        padding: 20,
        avoidOverlap: true,
        avoidOverlapPadding: 10,
        rows: undefined,
        cols: undefined,
      },
    }),
    [],
  );

  // Initialize Cytoscape
  useEffect(() => {
    if (!cyContainerRef.current) return;

    const cy = cytoscape({
      container: cyContainerRef.current,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#60a5fa",
            "border-color": "#3b82f6",
            "border-width": 2,
            label: "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            color: "#1f2937",
            "font-size": "12px",
            "font-weight": "bold",
            width: "30px",
            height: "30px",
            "text-wrap": "wrap",
            "text-max-width": "80px",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#6b7280",
            "target-arrow-color": "#6b7280",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": "10px",
            color: "#4b5563",
            "text-rotation": "autorotate",
            "text-margin-y": -10,
          },
        },
        {
          selector: "node:selected",
          style: {
            "background-color": "#f59e0b",
            "border-color": "#d97706",
            "border-width": 3,
          },
        },
        {
          selector: "edge:selected",
          style: {
            "line-color": "#f59e0b",
            "target-arrow-color": "#f59e0b",
            width: 3,
          },
        },
      ],
      elements: [],
      layout: layoutOptions[selectedLayout],
    });

    cyRef.current = cy;

    // Add event listeners
    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      console.log("Node tapped:", node.data());
    });

    cy.on("tap", "edge", (evt) => {
      const edge = evt.target;
      console.log("Edge tapped:", edge.data());
    });

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [layoutOptions, selectedLayout]);

  // Update graph data
  useEffect(() => {
    if (!cyRef.current || !graph?.elements) return;

    try {
      // Clear existing elements
      cyRef.current.elements().remove();

      // Add new elements
      cyRef.current.add(graph.elements);

      // Apply layout if fitOnUpdate is enabled
      if (fitOnUpdate) {
        const layout = cyRef.current.layout(layoutOptions[selectedLayout]);
        layout.run();
      }

      // Trigger callback
      if (onGraphUpdate) {
        onGraphUpdate({
          nodes: cyRef.current.nodes().length,
          edges: cyRef.current.edges().length,
        });
      }
    } catch (error) {
      console.error("Error updating graph:", error);
    }
  }, [graph, fitOnUpdate, selectedLayout, onGraphUpdate, layoutOptions]);

  // Apply layout
  const applyLayout = useCallback(
    async (layoutName = selectedLayout) => {
      if (!cyRef.current || layoutLoading) return;

      setLayoutLoading(true);
      try {
        // If using server-side layout calculation
        if (layoutName === "server") {
          const elements = cyRef.current.elements().jsons();
          const nodes = elements.filter(
            (el) => !el.data.source && !el.data.target,
          );
          const edges = elements.filter(
            (el) => el.data.source && el.data.target,
          );

          const response = await layoutAPI.calculateLayout({
            nodes,
            edges,
            layout: "spring",
          });

          if (response.data && response.data.nodes) {
            // Update node positions
            response.data.nodes.forEach((nodeData) => {
              const node = cyRef.current.getElementById(nodeData.id);
              if (node.length > 0) {
                node.position({
                  x: nodeData.position.x,
                  y: nodeData.position.y,
                });
              }
            });

            cyRef.current.fit();
          }
        } else {
          // Use client-side layout
          const layout = cyRef.current.layout(layoutOptions[layoutName]);
          layout.run();
        }
      } catch (error) {
        console.error("Error applying layout:", error);
      } finally {
        setLayoutLoading(false);
      }
    },
    [selectedLayout, layoutLoading, layoutOptions],
  );

  // Layout controls
  const handleLayoutChange = useCallback(
    (newLayout) => {
      setSelectedLayout(newLayout);
      applyLayout(newLayout);
    },
    [applyLayout],
  );

  // Graph controls
  const handleFit = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.fit();
    }
  }, []);

  const handleCenter = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.center();
    }
  }, []);

  const handleReset = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.zoom(1);
      cyRef.current.center();
    }
  }, []);

  const exportImage = useCallback(() => {
    if (cyRef.current) {
      const png64 = cyRef.current.png({ scale: 2 });
      const link = document.createElement("a");
      link.href = png64;
      link.download = "network-graph.png";
      link.click();
    }
  }, []);

  const getNodeCount = () => cyRef.current?.nodes().length || 0;
  const getEdgeCount = () => cyRef.current?.edges().length || 0;

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Controls */}
      {showControls && (
        <div className="flex-shrink-0 p-3 bg-gray-50 border-b border-gray-200">
          <div className="flex flex-wrap items-center justify-between gap-3">
            {/* Layout Selection */}
            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium text-gray-700">
                Layout:
              </label>
              <select
                value={selectedLayout}
                onChange={(e) => handleLayoutChange(e.target.value)}
                disabled={layoutLoading}
                className="text-sm px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="klay">Hierarchical (Klay)</option>
                <option value="cose">Force-directed (COSE)</option>
                <option value="breadthfirst">Breadth-first</option>
                <option value="circle">Circle</option>
                <option value="concentric">Concentric</option>
                <option value="grid">Grid</option>
                <option value="server">Server Layout</option>
              </select>
              {layoutLoading && (
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              )}
            </div>

            {/* View Controls */}
            <div className="flex items-center space-x-2">
              <button
                onClick={handleFit}
                className="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                title="Fit to view"
              >
                Fit
              </button>
              <button
                onClick={handleCenter}
                className="text-sm px-3 py-1 bg-gray-600 text-white rounded hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
                title="Center view"
              >
                Center
              </button>
              <button
                onClick={handleReset}
                className="text-sm px-3 py-1 bg-gray-600 text-white rounded hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
                title="Reset zoom"
              >
                Reset
              </button>
              <button
                onClick={exportImage}
                className="text-sm px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
                title="Export as PNG"
              >
                Export
              </button>
            </div>

            {/* Toggle Controls */}
            <div className="flex items-center space-x-3">
              <label className="flex items-center space-x-1 text-sm">
                <input
                  type="checkbox"
                  checked={fitOnUpdate}
                  onChange={(e) => setFitOnUpdate(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Auto-fit</span>
              </label>
              <button
                onClick={() => setShowControls(false)}
                className="text-gray-400 hover:text-gray-600 focus:outline-none"
                title="Hide controls"
              >
                <svg
                  className="w-4 h-4"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            </div>
          </div>

          {/* Graph Stats */}
          <div className="mt-2 flex items-center space-x-4 text-xs text-gray-500">
            <span>Nodes: {getNodeCount()}</span>
            <span>Edges: {getEdgeCount()}</span>
            {isLoading && (
              <span className="flex items-center space-x-1 text-blue-600">
                <div className="w-3 h-3 border border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                <span>Loading...</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Show Controls Button (when hidden) */}
      {!showControls && (
        <button
          onClick={() => setShowControls(true)}
          className="absolute top-2 right-2 z-10 p-2 bg-white border border-gray-300 rounded shadow-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          title="Show controls"
        >
          <svg
            className="w-4 h-4 text-gray-600"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      )}

      {/* Cytoscape Container */}
      <div
        ref={cyContainerRef}
        className="flex-1 relative bg-white"
        style={{ minHeight: "400px" }}
      />

      {/* Empty State */}
      {(!graph || !graph.elements || graph.elements.length === 0) &&
        !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <svg
                className="w-16 h-16 mx-auto mb-4 text-gray-300"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M2 3a1 1 0 00-1 1v1a1 1 0 001 1h16a1 1 0 001-1V4a1 1 0 00-1-1H2zm0 4.5h16l-.811 7.71a2 2 0 01-1.99 1.79H4.8a2 2 0 01-1.99-1.79L2 7.5z"
                  clipRule="evenodd"
                />
              </svg>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                No Network Data
              </h3>
              <p className="text-sm text-gray-500 max-w-sm">
                Upload network files, load sample data, or generate a network
                through chat to get started.
              </p>
            </div>
          </div>
        )}
    </div>
  );
};

export default NetworkVisualization;
