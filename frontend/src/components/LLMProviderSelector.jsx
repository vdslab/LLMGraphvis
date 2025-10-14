import { useState, useEffect } from "react";
import { settingsAPI } from "../services/api";

const MODEL_OPTIONS = {
  google: [
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { value: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite" },
    { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
  ],
  openai: [
    { value: "gpt-3.5-turbo", label: "ChatGPT o3 mini" },
    { value: "gpt-4-turbo", label: "ChatGPT o4 mini" },
    { value: "gpt-5-mini", label: "ChatGPT 5 mini" },
    { value: "gpt-5", label: "ChatGPT 5" },
    { value: "gpt-4o", label: "ChatGPT 4o" },
  ],
};

const LLMProviderSelector = () => {
  const [llmProvider, setLlmProvider] = useState("google");
  const [llmModel, setLlmModel] = useState("");
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState(null);

  // Fetch current LLM provider on mount
  useEffect(() => {
    const fetchLlmProvider = async () => {
      setLlmLoading(true);
      setLlmError(null);
      try {
        const res = await settingsAPI.getLLMProviderSettings();
        if (res.data && res.data.provider) {
          setLlmProvider(res.data.provider);
          if (res.data.openai_model) setLlmModel(res.data.openai_model);
          else if (res.data.provider === "google")
            setLlmModel("gemini-2.5-flash");
          else if (res.data.provider === "openai") setLlmModel("gpt-4o");
        }
      } catch {
        setLlmError("Failed to load LLM provider settings");
      } finally {
        setLlmLoading(false);
      }
    };
    fetchLlmProvider();
  }, []);

  // Handle LLM provider change
  const handleLlmProviderChange = async (e) => {
    const newProvider = e.target.value;
    setLlmLoading(true);
    setLlmError(null);
    try {
      // Default to first model for new provider
      const defaultModel = MODEL_OPTIONS[newProvider][0]?.value || "";

      // Build settings object based on provider
      const settings = { provider: newProvider };
      if (newProvider === "openai") {
        settings.openai_model = defaultModel;
      }

      await settingsAPI.updateLLMProviderSettings(settings);
      setLlmProvider(newProvider);
      setLlmModel(defaultModel);
    } catch {
      setLlmError("Failed to update LLM provider");
    } finally {
      setLlmLoading(false);
    }
  };

  // Handle LLM model change
  const handleLlmModelChange = async (e) => {
    const newModel = e.target.value;
    setLlmLoading(true);
    setLlmError(null);
    try {
      // Build settings object based on provider
      const settings = { provider: llmProvider };
      if (llmProvider === "openai") {
        settings.openai_model = newModel;
      }

      await settingsAPI.updateLLMProviderSettings(settings);
      setLlmModel(newModel);
    } catch {
      setLlmError("Failed to update LLM model");
    } finally {
      setLlmLoading(false);
    }
  };

  return (
    <div className="px-4 py-3 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
      <div className="flex flex-col space-y-3 sm:space-y-0 sm:flex-row sm:items-center sm:space-x-4">
        {/* Provider Selection */}
        <div className="flex items-center space-x-2">
          <label className="text-sm font-medium text-gray-700 min-w-0 whitespace-nowrap">
            Provider:
          </label>
          <select
            className="text-sm px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white min-w-0 flex-1 sm:flex-none sm:w-auto"
            value={llmProvider}
            onChange={handleLlmProviderChange}
            disabled={llmLoading}
          >
            <option value="google">Google (Gemini)</option>
            <option value="openai">OpenAI (ChatGPT)</option>
          </select>
        </div>

        {/* Model Selection */}
        <div className="flex items-center space-x-2">
          <label className="text-sm font-medium text-gray-700 min-w-0 whitespace-nowrap">
            Model:
          </label>
          <select
            className="text-sm px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white min-w-0 flex-1 sm:flex-none sm:w-auto"
            value={llmModel}
            onChange={handleLlmModelChange}
            disabled={llmLoading}
          >
            {(MODEL_OPTIONS[llmProvider] || []).map((model) => (
              <option key={model.value} value={model.value}>
                {model.label}
              </option>
            ))}
          </select>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center space-x-2 flex-1 justify-end">
          {llmLoading && (
            <div className="flex items-center space-x-2 text-blue-600">
              <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              <span className="text-sm font-medium">Switching...</span>
            </div>
          )}
          {llmError && (
            <div className="flex items-center space-x-1 text-red-600">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-sm font-medium">{llmError}</span>
            </div>
          )}
          {!llmLoading && !llmError && (
            <div className="flex items-center space-x-1 text-green-600">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-sm font-medium">Ready</span>
            </div>
          )}
        </div>
      </div>

      {/* Rate Limit Info */}
      <div className="mt-2 text-xs text-gray-500">
        Using shared API keys with rate limiting (100 requests/hour)
      </div>
    </div>
  );
};

export default LLMProviderSelector;
