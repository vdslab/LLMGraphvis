import { useState, useRef, useEffect } from "react";
import FileUploadButton from "../components/FileUploadButton";
import * as graphml from "graphml-js";
import { useForm } from "react-hook-form";
import ForceGraph2D from "react-force-graph-2d";
import useNetworkStore from "../services/networkStore";

const NetworkVisualizationPage = () => {
  const {
    setNetworkData,
    setLayout,
    setLayoutParams,
    calculateLayout,
    edges,
    positions,
    layout,
    layoutParams,
    isLoading,
    error,
  } = useNetworkStore();

  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [layoutParamsInput, setLayoutParamsInput] = useState("{}");
  const graphRef = useRef();

  // Handle GraphML file upload
  const handleGraphMLUpload = async (file) => {
    try {
      const text = await file.text();
      // Parse GraphML using graphml-js (or fallback to simple XML parsing)
      let parsed;
      try {
        parsed = graphml.parse(text);
      } catch (e) {
        // fallback: try DOMParser
        const parser = new window.DOMParser();
        const xmlDoc = parser.parseFromString(text, "text/xml");
        // Simple GraphML to nodes/edges extraction (basic, not robust)
        const nodeEls = xmlDoc.getElementsByTagName("node");
        const edgeEls = xmlDoc.getElementsByTagName("edge");
        const nodes = Array.from(nodeEls).map((n) => ({
          id: n.getAttribute("id"),
          label: n.getAttribute("id"),
        }));
        const edges = Array.from(edgeEls).map((e) => ({
          source: e.getAttribute("source"),
          target: e.getAttribute("target"),
        }));
        setNetworkData(nodes, edges);
        setLayout("spring");
        await calculateLayout();
        return;
      }
      // If using graphml-js
      const nodes = parsed.nodes.map((n) => ({ id: n.id, label: n.id }));
      const edges = parsed.edges.map((e) => ({
        source: e.source,
        target: e.target,
      }));
      setNetworkData(nodes, edges);
      setLayout("spring");
      await calculateLayout();
    } catch (e) {
      alert("Failed to parse GraphML: " + e.message);
    }
  };

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  // Convert positions to graph data format for ForceGraph
  useEffect(() => {
    if (positions.length > 0) {
      const graphNodes = positions.map((node) => ({
        id: node.id,
        x: node.x * 100, // Scale for better visualization
        y: node.y * 100,
        label: node.label || node.id,
      }));

      const graphLinks = edges.map((edge) => ({
        source: edge.source,
        target: edge.target,
      }));

      setGraphData({ nodes: graphNodes, links: graphLinks });
    }
  }, [positions, edges]);

  const onSubmit = async (data) => {
    try {
      // Parse nodes and edges from input
      const parsedNodes = data.nodes
        .split("\n")
        .filter((line) => line.trim())
        .map((line) => {
          const [id, label] = line.split(",").map((s) => s.trim());
          return { id, label: label || id };
        });

      const parsedEdges = data.edges
        .split("\n")
        .filter((line) => line.trim())
        .map((line) => {
          const [source, target] = line.split(",").map((s) => s.trim());
          return { source, target };
        });

      // Set network data
      setNetworkData(parsedNodes, parsedEdges);

      // Set layout
      setLayout(data.layout);

      // Set layout parameters if provided
      if (showAdvanced && layoutParamsInput) {
        try {
          const params = JSON.parse(layoutParamsInput);
          setLayoutParams(params);
        } catch (e) {
          console.error("Invalid JSON for layout parameters:", e);
        }
      }

      // Calculate layout
      await calculateLayout();
    } catch (e) {
      console.error("Error processing network data:", e);
    }
  };

  return (
    <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <h1 className="text-2xl font-semibold text-gray-900">
          Network Visualization
        </h1>
        <p className="mt-2 text-gray-600">
          Enter your network data and choose a layout algorithm to visualize it.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900">
                Network Data Input
              </h3>
              <div className="mt-5">
                {/* Upload GraphML Button */}
                <div className="mb-4">
                  <FileUploadButton
                    buttonText="Upload GraphML File"
                    className="mb-2"
                    onFileUpload={handleGraphMLUpload}
                  />
                  <p className="text-xs text-gray-500">Supported: .graphml</p>
                </div>
                <form onSubmit={handleSubmit(onSubmit)}>
                  <div className="mb-4">
                    <label
                      htmlFor="nodes"
                      className="block text-sm font-medium text-gray-700"
                    >
                      Nodes (one per line, format: id,label)
                    </label>
                    <div className="mt-1">
                      <textarea
                        id="nodes"
                        name="nodes"
                        rows={5}
                        className="shadow-sm focus:ring-blue-500 focus:border-blue-500 block w-full sm:text-sm border-gray-300 rounded-md font-mono"
                        placeholder="1,Node 1&#10;2,Node 2&#10;3,Node 3"
                        {...register("nodes", {
                          required: "Nodes are required",
                        })}
                      />
                      {errors.nodes && (
                        <p className="mt-1 text-sm text-red-600">
                          {errors.nodes.message}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="mb-4">
                    <label
                      htmlFor="edges"
                      className="block text-sm font-medium text-gray-700"
                    >
                      Edges (one per line, format: source,target)
                    </label>
                    <div className="mt-1">
                      <textarea
                        id="edges"
                        name="edges"
                        rows={5}
                        className="shadow-sm focus:ring-blue-500 focus:border-blue-500 block w-full sm:text-sm border-gray-300 rounded-md font-mono"
                        placeholder="1,2&#10;2,3&#10;3,1"
                        {...register("edges", {
                          required: "Edges are required",
                        })}
                      />
                      {errors.edges && (
                        <p className="mt-1 text-sm text-red-600">
                          {errors.edges.message}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="mb-4">
                    <label
                      htmlFor="layout"
                      className="block text-sm font-medium text-gray-700"
                    >
                      Layout Algorithm
                    </label>
                    <div className="mt-1">
                      <select
                        id="layout"
                        name="layout"
                        className="shadow-sm focus:ring-blue-500 focus:border-blue-500 block w-full sm:text-sm border-gray-300 rounded-md"
                        {...register("layout", {
                          required: "Layout is required",
                        })}
                        defaultValue="spring"
                      >
                        <optgroup label="Force-Directed Layouts">
                          <option value="spring">Spring Layout</option>
                          <option value="kamada_kawai">
                            Kamada-Kawai Layout
                          </option>
                          <option value="fruchterman_reingold">
                            Fruchterman-Reingold Layout
                          </option>
                        </optgroup>
                        <optgroup label="Geometric Layouts">
                          <option value="circular">Circular Layout</option>
                          <option value="grid">Grid Layout</option>
                          <option value="spiral">Spiral Layout</option>
                          <option value="planar">Planar Layout</option>
                        </optgroup>
                        <optgroup label="Hierarchical Layouts">
                          <option value="tree">Tree Layout</option>
                          <option value="radial">Radial Layout</option>
                          <option value="shell">Shell Layout</option>
                        </optgroup>
                        <optgroup label="Specialized Layouts">
                          <option value="bipartite">Bipartite Layout</option>
                          <option value="multipartite">
                            Multipartite Layout
                          </option>
                          <option value="spectral">Spectral Layout</option>
                        </optgroup>
                        <optgroup label="Other">
                          <option value="random">Random Layout</option>
                        </optgroup>
                      </select>
                      {errors.layout && (
                        <p className="mt-1 text-sm text-red-600">
                          {errors.layout.message}
                        </p>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-gray-500">
                      Choose a layout algorithm based on your network structure.
                      Force-directed layouts work well for general networks,
                      geometric layouts for structured data, and hierarchical
                      layouts for tree-like structures.
                    </p>
                  </div>

                  <div className="mb-4">
                    <button
                      type="button"
                      className="text-sm text-blue-600 hover:text-blue-500"
                      onClick={() => setShowAdvanced(!showAdvanced)}
                    >
                      {showAdvanced
                        ? "Hide Advanced Options"
                        : "Show Advanced Options"}
                    </button>
                  </div>

                  {showAdvanced && (
                    <div className="mb-4">
                      <label
                        htmlFor="layoutParams"
                        className="block text-sm font-medium text-gray-700"
                      >
                        Layout Parameters (JSON)
                      </label>
                      <div className="mt-1">
                        <textarea
                          id="layoutParams"
                          name="layoutParams"
                          rows={3}
                          className="shadow-sm focus:ring-blue-500 focus:border-blue-500 block w-full sm:text-sm border-gray-300 rounded-md font-mono"
                          placeholder='{"k": 0.5, "iterations": 50}'
                          value={layoutParamsInput}
                          onChange={(e) => setLayoutParamsInput(e.target.value)}
                        />
                      </div>
                    </div>
                  )}

                  {error && (
                    <div className="mb-4 rounded-md bg-red-50 p-4">
                      <div className="flex">
                        <div className="ml-3">
                          <h3 className="text-sm font-medium text-red-800">
                            {error}
                          </h3>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={isLoading}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-blue-300"
                    >
                      {isLoading
                        ? "Calculating Layout..."
                        : "Visualize Network"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>

          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900">
                Network Visualization
              </h3>
              <div className="mt-5">
                {graphData.nodes.length > 0 ? (
                  <div
                    className="border border-gray-200 rounded-md"
                    style={{ height: "500px" }}
                  >
                    <ForceGraph2D
                      ref={graphRef}
                      graphData={graphData}
                      nodeLabel="label"
                      nodeColor={() => "#1d4ed8"}
                      linkColor={() => "#94a3b8"}
                      nodeRelSize={5}
                      linkWidth={1}
                      d3AlphaDecay={0}
                      d3VelocityDecay={0.4}
                      cooldownTime={2000}
                      onEngineStop={() => {
                        if (graphRef.current) {
                          graphRef.current.d3Force("charge").strength(-120);
                          graphRef.current.d3Force("link").strength(0.8);
                          graphRef.current.d3Force("center", null);
                        }
                      }}
                    />
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <svg
                      className="mx-auto h-12 w-12 text-gray-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
                      />
                    </svg>
                    <h3 className="mt-2 text-sm font-medium text-gray-900">
                      No network data
                    </h3>
                    <p className="mt-1 text-sm text-gray-500">
                      Enter network data and click "Visualize Network" to see
                      the visualization.
                    </p>
                  </div>
                )}
              </div>

              {graphData.nodes.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700">
                    Current Layout: {layout}
                  </h4>
                  {Object.keys(layoutParams).length > 0 && (
                    <div className="mt-1">
                      <h5 className="text-xs font-medium text-gray-600">
                        Parameters:
                      </h5>
                      <pre className="mt-1 text-xs text-gray-500 bg-gray-50 p-2 rounded-md">
                        {JSON.stringify(layoutParams, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="mt-8 bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">
              Example Network Data
            </h3>
            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="bg-gray-50 p-4 rounded-md">
                <h4 className="text-sm font-medium text-gray-700">
                  Simple Triangle
                </h4>
                <div className="mt-2">
                  <p className="text-xs font-medium text-gray-600">Nodes:</p>
                  <pre className="mt-1 text-xs text-gray-500">
                    1,Node 1 2,Node 2 3,Node 3
                  </pre>
                  <p className="mt-2 text-xs font-medium text-gray-600">
                    Edges:
                  </p>
                  <pre className="mt-1 text-xs text-gray-500">1,2 2,3 3,1</pre>
                </div>
              </div>
              <div className="bg-gray-50 p-4 rounded-md">
                <h4 className="text-sm font-medium text-gray-700">
                  Star Network
                </h4>
                <div className="mt-2">
                  <p className="text-xs font-medium text-gray-600">Nodes:</p>
                  <pre className="mt-1 text-xs text-gray-500">
                    center,Center 1,Node 1 2,Node 2 3,Node 3 4,Node 4 5,Node 5
                  </pre>
                  <p className="mt-2 text-xs font-medium text-gray-600">
                    Edges:
                  </p>
                  <pre className="mt-1 text-xs text-gray-500">
                    center,1 center,2 center,3 center,4 center,5
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NetworkVisualizationPage;
