import { useState, useEffect, useRef } from "react";
import { networkChatAPI } from "../services/api";

const ChatPanel = ({
  isLoading,
  setIsLoading,
  onChatResponse,
  graph,
  files,
}) => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Scroll to bottom when new messages added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputText]);

  const handleSendMessage = async () => {
    if (!inputText.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: "user",
      text: inputText.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputText("");
    setIsLoading(true);

    try {
      // Create FormData for file uploads
      const formData = new FormData();
      formData.append("message", userMessage.text);

      // Add graph data if available
      if (graph && graph.elements && graph.elements.length > 0) {
        const networkData = {
          nodes: graph.elements.filter(
            (el) => !el.data.source && !el.data.target,
          ),
          edges: graph.elements.filter(
            (el) => el.data.source && el.data.target,
          ),
        };
        formData.append("network_data", JSON.stringify(networkData));
      }

      // Add uploaded files
      files.forEach((file) => {
        formData.append("files", file);
      });

      const response = await networkChatAPI.sendMessage(formData);

      const assistantMessage = {
        id: Date.now() + 1,
        type: "assistant",
        text: response.data.message,
        timestamp: new Date(),
        analysis: response.data.analysis,
        recommendations: response.data.recommendations,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Call parent callback with response
      if (onChatResponse) {
        onChatResponse(response.data);
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      const errorMessage = {
        id: Date.now() + 1,
        type: "error",
        text: "Failed to send message. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTimestamp = (timestamp) => {
    return timestamp.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const renderMessage = (message) => {
    const baseClasses = "flex items-start space-x-3 p-4 rounded-lg";
    const userClasses = "bg-blue-50 ml-8";
    const assistantClasses = "bg-gray-50 mr-8";
    const errorClasses = "bg-red-50 mr-8";

    let containerClasses = baseClasses;
    let iconColor = "";
    let icon = null;

    if (message.type === "user") {
      containerClasses += ` ${userClasses}`;
      iconColor = "text-blue-600";
      icon = (
        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
            clipRule="evenodd"
          />
        </svg>
      );
    } else if (message.type === "assistant") {
      containerClasses += ` ${assistantClasses}`;
      iconColor = "text-green-600";
      icon = (
        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M4 4a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2H4zm2 6a2 2 0 114 0 2 2 0 01-4 0zm8 0a2 2 0 114 0 2 2 0 01-4 0z"
            clipRule="evenodd"
          />
        </svg>
      );
    } else {
      containerClasses += ` ${errorClasses}`;
      iconColor = "text-red-600";
      icon = (
        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clipRule="evenodd"
          />
        </svg>
      );
    }

    return (
      <div key={message.id} className={containerClasses}>
        <div className={`flex-shrink-0 ${iconColor}`}>{icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <p className="text-sm font-medium text-gray-900">
              {message.type === "user"
                ? "You"
                : message.type === "assistant"
                  ? "Assistant"
                  : "Error"}
            </p>
            <p className="text-xs text-gray-500">
              {formatTimestamp(message.timestamp)}
            </p>
          </div>
          <div className="text-sm text-gray-700 whitespace-pre-wrap break-words">
            {message.text}
          </div>

          {/* Analysis section */}
          {message.analysis && (
            <div className="mt-3 p-3 bg-blue-50 rounded-md">
              <h4 className="text-sm font-medium text-blue-900 mb-2">
                Analysis
              </h4>
              <div className="text-sm text-blue-800 whitespace-pre-wrap">
                {message.analysis}
              </div>
            </div>
          )}

          {/* Recommendations section */}
          {message.recommendations && message.recommendations.length > 0 && (
            <div className="mt-3 p-3 bg-green-50 rounded-md">
              <h4 className="text-sm font-medium text-green-900 mb-2">
                Recommendations
              </h4>
              <ul className="text-sm text-green-800 space-y-1">
                {message.recommendations.map((rec, index) => (
                  <li key={index} className="flex items-start">
                    <span className="mr-2">•</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <svg
              className="w-12 h-12 mx-auto mb-4 text-gray-300"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M18 13V5a2 2 0 00-2-2H4a2 2 0 00-2 2v8a2 2 0 002 2h3l3 3 3-3h3a2 2 0 002-2zM5 7a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1zm1 3a1 1 0 100 2h3a1 1 0 100-2H6z"
                clipRule="evenodd"
              />
            </svg>
            <p className="text-lg font-medium">Welcome to Network Chat</p>
            <p className="text-sm mt-1">
              Ask questions about your network data, upload files, or request
              analysis.
            </p>
          </div>
        ) : (
          messages.map(renderMessage)
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-start space-x-3 p-4 rounded-lg bg-gray-50 mr-8">
            <div className="flex-shrink-0 text-green-600">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M4 4a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2H4zm2 6a2 2 0 114 0 2 2 0 01-4 0zm8 0a2 2 0 114 0 2 2 0 01-4 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-600 rounded-full animate-bounce"></div>
                <div
                  className="w-2 h-2 bg-green-600 rounded-full animate-bounce"
                  style={{ animationDelay: "0.1s" }}
                ></div>
                <div
                  className="w-2 h-2 bg-green-600 rounded-full animate-bounce"
                  style={{ animationDelay: "0.2s" }}
                ></div>
                <span className="text-sm text-gray-600">
                  Assistant is thinking...
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Container */}
      <div className="border-t border-gray-200 p-4 bg-white">
        <div className="flex items-end space-x-3">
          <textarea
            ref={textareaRef}
            className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm min-h-[40px] max-h-32"
            placeholder="Ask about your network data, request analysis, or upload files..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
            rows={1}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputText.trim() || isLoading}
            className="flex-shrink-0 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        {/* Context indicators */}
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
          <div className="flex items-center space-x-4">
            {graph && graph.elements && graph.elements.length > 0 && (
              <span className="flex items-center space-x-1">
                <svg
                  className="w-3 h-3 text-green-600"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                <span>Network data available</span>
              </span>
            )}
            {files && files.length > 0 && (
              <span className="flex items-center space-x-1">
                <svg
                  className="w-3 h-3 text-blue-600"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                    clipRule="evenodd"
                  />
                </svg>
                <span>{files.length} file(s) ready</span>
              </span>
            )}
          </div>
          <span>Press Enter to send, Shift+Enter for new line</span>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
