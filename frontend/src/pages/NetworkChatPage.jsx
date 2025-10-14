import { useState } from "react";
import useNetworkStore from "../services/networkStore";
import LLMProviderSelector from "../components/LLMProviderSelector";
import ChatPanel from "../components/ChatPanel";
import FileUploadHandler from "../components/FileUploadHandler";
import FileUploadButton from "../components/FileUploadButton";
import NetworkVisualization from "../components/NetworkVisualization";

const NetworkChatPage = () => {
  const {
    nodes,
    edges,
    isLoading,
    setNetworkData,
    calculateLayout,
    setLayout,
  } = useNetworkStore();
  const [files, setFiles] = useState([]);

  // Handle GraphML file upload for direct network visualization
  const handleGraphMLUpload = async (file) => {
    try {
      const text = await file.text();

      // Simple GraphML parsing using DOMParser
      const parser = new window.DOMParser();
      const xmlDoc = parser.parseFromString(text, "text/xml");

      // Check for XML parsing errors
      const parserError = xmlDoc.querySelector("parsererror");
      if (parserError) {
        throw new Error("Invalid XML format");
      }

      // Extract nodes and edges from GraphML
      const nodeElements = xmlDoc.getElementsByTagName("node");
      const edgeElements = xmlDoc.getElementsByTagName("edge");

      const parsedNodes = Array.from(nodeElements).map((nodeEl) => {
        const id = nodeEl.getAttribute("id");
        // Try to get label from data element or use id as label
        const dataEl = nodeEl.querySelector('data[key="label"]');
        const label = dataEl ? dataEl.textContent : id;
        return { id, label };
      });

      const parsedEdges = Array.from(edgeElements).map((edgeEl) => ({
        source: edgeEl.getAttribute("source"),
        target: edgeEl.getAttribute("target"),
      }));

      if (parsedNodes.length === 0) {
        throw new Error("No nodes found in GraphML file");
      }

      // Set network data and calculate layout
      setNetworkData(parsedNodes, parsedEdges);
      setLayout("spring");
      await calculateLayout();

      // Also add the file to the files list for chat context
      setFiles((prev) => [...prev, file]);

      console.log(
        `Loaded GraphML: ${parsedNodes.length} nodes, ${parsedEdges.length} edges`,
      );
    } catch (error) {
      console.error("Failed to parse GraphML:", error);
      alert(`Failed to parse GraphML file: ${error.message}`);
    }
  };

  return (
    <div className="flex flex-col h-full w-full">
      {/* LLM Provider Selector */}
      <LLMProviderSelector />

      <div className="flex flex-1 flex-col md:flex-row overflow-hidden">
        {/* Left: Chat and File Upload */}
        <div className="w-full md:w-1/3 flex flex-col border-r border-gray-200 bg-gray-50 h-full">
          <div className="p-4 border-b border-gray-200">
            {/* GraphML Upload Button */}
            <div className="mb-4">
              <FileUploadButton
                buttonText="Upload GraphML Network"
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-center"
                onFileUpload={handleGraphMLUpload}
              />
              <p className="text-xs text-gray-500 mt-1 text-center">
                Directly load and visualize GraphML network data
              </p>
            </div>

            {/* General File Upload */}
            <FileUploadHandler files={files} setFiles={setFiles} />
          </div>
          <div className="flex-1 min-h-0">
            <ChatPanel
              isLoading={isLoading}
              setIsLoading={() => {}}
              onChatResponse={() => {}}
              graph={{ elements: [...nodes, ...edges] }}
              files={files}
            />
          </div>
        </div>

        {/* Right: Network Visualization */}
        <div className="flex-1 min-w-0 h-full">
          <NetworkVisualization
            graph={{ elements: [...nodes, ...edges] }}
            isLoading={isLoading}
            onGraphUpdate={() => {}}
          />
        </div>
      </div>
    </div>
  );
};

export default NetworkChatPage;
