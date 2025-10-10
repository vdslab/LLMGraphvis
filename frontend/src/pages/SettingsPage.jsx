import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import useSettingsStore from "../services/settingsStore";

const SettingsPage = () => {
  const {
    llmSettings,
    llmStatus,
    isLoading,
    isUpdating,
    error,
    updateSuccess,
    fetchLLMSettings,
    updateLLMSettings,
    fetchLLMStatus,
    clearError,
    clearUpdateSuccess,
  } = useSettingsStore();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm();
  const [showApiKeys, setShowApiKeys] = useState(false);

  const watchedProvider = watch("provider");

  useEffect(() => {
    // Initialize settings on component mount
    fetchLLMSettings();
    fetchLLMStatus();
  }, [fetchLLMSettings, fetchLLMStatus]);

  useEffect(() => {
    // Update form when settings are loaded
    if (llmSettings) {
      setValue("provider", llmSettings.provider);
      setValue("openai_model", llmSettings.openai_model);
    }
  }, [llmSettings, setValue]);

  useEffect(() => {
    // Clear messages when they're displayed
    if (error || updateSuccess) {
      const timer = setTimeout(() => {
        clearError();
        clearUpdateSuccess();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, updateSuccess, clearError, clearUpdateSuccess]);

  const onSubmit = async (data) => {
    try {
      const updateData = {
        provider: data.provider,
      };

      // Only include API keys if they are provided
      if (data.google_api_key && data.google_api_key.trim()) {
        updateData.google_api_key = data.google_api_key.trim();
      }

      if (data.openai_api_key && data.openai_api_key.trim()) {
        updateData.openai_api_key = data.openai_api_key.trim();
      }

      if (data.openai_model && data.openai_model.trim()) {
        updateData.openai_model = data.openai_model.trim();
      }

      await updateLLMSettings(updateData);
      // Refresh status after update
      await fetchLLMStatus();
    } catch (err) {
      console.error("Failed to update settings:", err);
    }
  };

  const handleTestConnection = async () => {
    await fetchLLMStatus();
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2">Loading settings...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <h1 className="text-2xl font-semibold text-gray-900">
          LLM Provider Settings
        </h1>
        <p className="mt-2 text-gray-600">
          Configure your Large Language Model provider and API keys.
        </p>

        {/* Status Messages */}
        {error && (
          <div className="mt-4 rounded-md bg-red-50 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg
                  className="h-5 w-5 text-red-400"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <div className="mt-2 text-sm text-red-700">{error}</div>
              </div>
            </div>
          </div>
        )}

        {updateSuccess && (
          <div className="mt-4 rounded-md bg-green-50 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg
                  className="h-5 w-5 text-green-400"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-green-800">Success</h3>
                <div className="mt-2 text-sm text-green-700">
                  Settings updated successfully!
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Current Status */}
        <div className="mt-8 bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">
              Current Status
            </h3>
            <div className="mt-5">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div>
                  <dt className="text-sm font-medium text-gray-500">
                    Provider
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {llmStatus.provider}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Status</dt>
                  <dd className="mt-1">
                    <span
                      className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        llmStatus.status === "ready"
                          ? "bg-green-100 text-green-800"
                          : llmStatus.status === "error"
                            ? "bg-red-100 text-red-800"
                            : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      {llmStatus.status}
                    </span>
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-sm font-medium text-gray-500">Message</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {llmStatus.message}
                  </dd>
                </div>
              </div>
              <div className="mt-4">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Test Connection
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Settings Form */}
        <div className="mt-8 bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">
              Configure Settings
            </h3>
            <form onSubmit={handleSubmit(onSubmit)} className="mt-5 space-y-6">
              {/* Provider Selection */}
              <div>
                <label
                  htmlFor="provider"
                  className="block text-sm font-medium text-gray-700"
                >
                  LLM Provider
                </label>
                <select
                  id="provider"
                  {...register("provider", {
                    required: "Provider is required",
                  })}
                  className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
                >
                  <option value="google">Google Gemini</option>
                  <option value="openai">OpenAI</option>
                </select>
                {errors.provider && (
                  <p className="mt-1 text-sm text-red-600">
                    {errors.provider.message}
                  </p>
                )}
              </div>

              {/* API Keys Section */}
              <div>
                <div className="flex items-center justify-between">
                  <h4 className="text-base font-medium text-gray-900">
                    API Keys
                  </h4>
                  <button
                    type="button"
                    onClick={() => setShowApiKeys(!showApiKeys)}
                    className="text-sm text-blue-600 hover:text-blue-500"
                  >
                    {showApiKeys ? "Hide" : "Show"} API Keys
                  </button>
                </div>

                {showApiKeys && (
                  <div className="mt-4 space-y-4">
                    {/* Google API Key */}
                    <div>
                      <label
                        htmlFor="google_api_key"
                        className="block text-sm font-medium text-gray-700"
                      >
                        Google API Key
                        {llmSettings.has_google_api_key && (
                          <span className="ml-2 text-xs text-green-600">
                            (Currently set)
                          </span>
                        )}
                      </label>
                      <input
                        type="password"
                        id="google_api_key"
                        {...register("google_api_key")}
                        className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        placeholder="Enter your Google API key"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Leave empty to keep current key. Get your key from{" "}
                        <a
                          href="https://aistudio.google.com/app/apikey"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-500"
                        >
                          Google AI Studio
                        </a>
                      </p>
                    </div>

                    {/* OpenAI API Key */}
                    <div>
                      <label
                        htmlFor="openai_api_key"
                        className="block text-sm font-medium text-gray-700"
                      >
                        OpenAI API Key
                        {llmSettings.has_openai_api_key && (
                          <span className="ml-2 text-xs text-green-600">
                            (Currently set)
                          </span>
                        )}
                      </label>
                      <input
                        type="password"
                        id="openai_api_key"
                        {...register("openai_api_key")}
                        className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        placeholder="Enter your OpenAI API key"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Leave empty to keep current key. Get your key from{" "}
                        <a
                          href="https://platform.openai.com/api-keys"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-500"
                        >
                          OpenAI Platform
                        </a>
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* OpenAI Model Selection */}
              {watchedProvider === "openai" && (
                <div>
                  <label
                    htmlFor="openai_model"
                    className="block text-sm font-medium text-gray-700"
                  >
                    OpenAI Model
                  </label>
                  <select
                    id="openai_model"
                    {...register("openai_model")}
                    className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
                  >
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="gpt-4o-mini">GPT-4o Mini</option>
                    <option value="gpt-4-turbo">GPT-4 Turbo</option>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                  </select>
                </div>
              )}

              {/* Submit Button */}
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isUpdating}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-blue-300"
                >
                  {isUpdating ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Updating...
                    </>
                  ) : (
                    "Update Settings"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Help Section */}
        <div className="mt-8 bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">
              Help
            </h3>
            <div className="mt-5">
              <div className="prose prose-sm text-gray-500">
                <h4>Provider Information:</h4>
                <ul>
                  <li>
                    <strong>Google Gemini:</strong> Fast and efficient, good for
                    general tasks. Free tier with rate limits.
                  </li>
                  <li>
                    <strong>OpenAI:</strong> High-quality responses, good for
                    complex reasoning. Paid service with higher rate limits.
                  </li>
                </ul>

                <h4>Getting API Keys:</h4>
                <ul>
                  <li>
                    <strong>Google:</strong> Visit{" "}
                    <a
                      href="https://aistudio.google.com/app/apikey"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Google AI Studio
                    </a>{" "}
                    to create a free API key.
                  </li>
                  <li>
                    <strong>OpenAI:</strong> Visit{" "}
                    <a
                      href="https://platform.openai.com/api-keys"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      OpenAI Platform
                    </a>{" "}
                    to create an API key (requires account with billing).
                  </li>
                </ul>

                <p>
                  <strong>Note:</strong> API keys are stored securely and only
                  used for your requests. Changes take effect immediately
                  without restarting the application.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
