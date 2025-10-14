import { useState } from "react";
import useNetworkStore from "../services/networkStore";
import LLMProviderSelector from "../components/LLMProviderSelector";
import ChatPanel from "../components/ChatPanel";
import FileUploadHandler from "../components/FileUploadHandler";
import NetworkVisualization from "../components/NetworkVisualization";

const NetworkChatPage = () => {
  const { nodes, edges, isLoading } = useNetworkStore();
  const [files, setFiles] = useState([]);

  return (
    <div className="flex flex-col h-full w-full">
      {/* LLM Provider Selector */}
      <LLMProviderSelector />

      <div className="flex flex-1 flex-col md:flex-row overflow-hidden">
        {/* Left: Chat and File Upload */}
        <div className="w-full md:w-1/3 flex flex-col border-r border-gray-200 bg-gray-50 h-full">
          <div className="p-4 border-b border-gray-200">
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
