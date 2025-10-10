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
      <div className="min-h-screen bg-gray-50 py-12">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <div className="flex min-h-[400px] items-center justify-center">
            <div className="text-center">
              <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600"></div>
              <p className="mt-4 text-lg font-medium text-gray-900">
                Loading settings...
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            LLM Provider Settings
          </h1>
          <p className="mt-2 text-lg text-gray-600">
            Configure your Large Language Model provider and API keys.
          </p>
        </div>

        {/* Status Messages */}
        {error && (
          <div className="mb-8 rounded-xl bg-red-50 p-4 ring-1 ring-red-200">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg
                  className="h-5 w-5 text-red-400"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-semibold text-red-800">Error</h3>
                <div className="mt-1 text-sm text-red-700">{error}</div>
              </div>
            </div>
          </div>
        )}

        {updateSuccess && (
          <div className="mb-8 rounded-xl bg-green-50 p-4 ring-1 ring-green-200">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg
                  className="h-5 w-5 text-green-400"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.236 4.53L7.53 10.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-semibold text-green-800">
                  Success
                </h3>
                <div className="mt-1 text-sm text-green-700">
                  Settings updated successfully!
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-8">
          {/* Current Status */}
          <div className="card">
            <div className="card-header">
              <h3 className="text-lg font-semibold text-gray-900">
                Current Status
              </h3>
            </div>
            <div className="card-body">
              <dl className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div>
                  <dt className="text-sm font-medium text-gray-500">
                    Provider
                  </dt>
                  <dd className="mt-1 text-sm font-semibold text-gray-900">
                    {llmStatus.provider === "google"
                      ? "Google Gemini"
                      : "OpenAI"}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Status</dt>
                  <dd className="mt-1">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        llmStatus.status === "ready"
                          ? "bg-green-100 text-green-800"
                          : llmStatus.status === "error"
                            ? "bg-red-100 text-red-800"
                            : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      <svg
                        className={`-ml-0.5 mr-1.5 h-2 w-2 ${
                          llmStatus.status === "ready"
                            ? "fill-green-400"
                            : llmStatus.status === "error"
                              ? "fill-red-400"
                              : "fill-yellow-400"
                        }`}
                        viewBox="0 0 6 6"
                        aria-hidden="true"
                      >
                        <circle cx={3} cy={3} r={3} />
                      </svg>
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
              </dl>
              <div className="mt-6">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  className="btn-secondary"
                >
                  Test Connection
                </button>
              </div>
            </div>
          </div>

          {/* Settings Form */}
          <div className="card">
            <div className="card-header">
              <h3 className="text-lg font-semibold text-gray-900">
                Configure Settings
              </h3>
            </div>
            <div className="card-body">
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
                {/* Provider Selection */}
                <div>
                  <label
                    htmlFor="provider"
                    className="block text-sm font-medium text-gray-900"
                  >
                    LLM Provider
                  </label>
                  <select
                    id="provider"
                    {...register("provider", {
                      required: "Provider is required",
                    })}
                    className="form-select mt-2"
                  >
                    <option value="google">Google Gemini</option>
                    <option value="openai">OpenAI</option>
                  </select>
                  {errors.provider && (
                    <p className="mt-2 text-sm text-red-600">
                      {errors.provider.message}
                    </p>
                  )}
                </div>

                {/* API Keys Section */}
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <h4 className="text-base font-semibold text-gray-900">
                      API Keys
                    </h4>
                    <button
                      type="button"
                      onClick={() => setShowApiKeys(!showApiKeys)}
                      className="text-sm font-medium text-primary-600 hover:text-primary-500 transition-colors duration-200"
                    >
                      {showApiKeys ? "Hide" : "Show"} API Keys
                    </button>
                  </div>

                  {showApiKeys && (
                    <div className="space-y-6 rounded-lg bg-gray-50 p-6">
                      {/* Google API Key */}
                      <div>
                        <label
                          htmlFor="google_api_key"
                          className="block text-sm font-medium text-gray-900"
                        >
                          Google API Key
                          {llmSettings.has_google_api_key && (
                            <span className="ml-2 inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-700/10">
                              Currently set
                            </span>
                          )}
                        </label>
                        <input
                          type="password"
                          id="google_api_key"
                          {...register("google_api_key")}
                          className="form-input mt-2"
                          placeholder="Enter your Google API key"
                        />
                        <p className="mt-2 text-xs text-gray-600">
                          Leave empty to keep current key. Get your key from{" "}
                          <a
                            href="https://aistudio.google.com/app/apikey"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-primary-600 hover:text-primary-500"
                          >
                            Google AI Studio
                          </a>
                        </p>
                      </div>

                      {/* OpenAI API Key */}
                      <div>
                        <label
                          htmlFor="openai_api_key"
                          className="block text-sm font-medium text-gray-900"
                        >
                          OpenAI API Key
                          {llmSettings.has_openai_api_key && (
                            <span className="ml-2 inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-700/10">
                              Currently set
                            </span>
                          )}
                        </label>
                        <input
                          type="password"
                          id="openai_api_key"
                          {...register("openai_api_key")}
                          className="form-input mt-2"
                          placeholder="Enter your OpenAI API key"
                        />
                        <p className="mt-2 text-xs text-gray-600">
                          Leave empty to keep current key. Get your key from{" "}
                          <a
                            href="https://platform.openai.com/api-keys"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-primary-600 hover:text-primary-500"
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
                  <div className="rounded-lg bg-blue-50 p-6">
                    <label
                      htmlFor="openai_model"
                      className="block text-sm font-medium text-gray-900"
                    >
                      OpenAI Model
                    </label>
                    <select
                      id="openai_model"
                      {...register("openai_model")}
                      className="form-select mt-2"
                    >
                      <option value="gpt-4o">GPT-4o</option>
                      <option value="gpt-4o-mini">GPT-4o Mini</option>
                      <option value="gpt-4-turbo">GPT-4 Turbo</option>
                      <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    </select>
                  </div>
                )}

                {/* Submit Button */}
                <div className="flex justify-end border-t border-gray-200 pt-6">
                  <button
                    type="submit"
                    disabled={isUpdating}
                    className="btn-primary"
                  >
                    {isUpdating ? (
                      <>
                        <svg
                          className="-ml-1 mr-3 h-5 w-5 animate-spin text-white"
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          ></circle>
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                          ></path>
                        </svg>
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
          <div className="card">
            <div className="card-header">
              <h3 className="text-lg font-semibold text-gray-900">Help</h3>
            </div>
            <div className="card-body">
              <div className="prose prose-sm max-w-none text-gray-600">
                <div className="grid gap-6 sm:grid-cols-2">
                  <div>
                    <h4 className="font-semibold text-gray-900">
                      Provider Information
                    </h4>
                    <ul className="mt-2 space-y-2">
                      <li className="flex">
                        <span className="font-medium text-gray-900 min-w-0 flex-1">
                          Google Gemini:
                        </span>
                        <span className="text-gray-600 ml-2">
                          Fast and efficient, good for general tasks. Free tier
                          with rate limits.
                        </span>
                      </li>
                      <li className="flex">
                        <span className="font-medium text-gray-900 min-w-0 flex-1">
                          OpenAI:
                        </span>
                        <span className="text-gray-600 ml-2">
                          High-quality responses, good for complex reasoning.
                          Paid service with higher rate limits.
                        </span>
                      </li>
                    </ul>
                  </div>

                  <div>
                    <h4 className="font-semibold text-gray-900">
                      Getting API Keys
                    </h4>
                    <ul className="mt-2 space-y-2">
                      <li>
                        <span className="font-medium text-gray-900">
                          Google:
                        </span>{" "}
                        Visit{" "}
                        <a
                          href="https://aistudio.google.com/app/apikey"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-primary-600 hover:text-primary-500"
                        >
                          Google AI Studio
                        </a>{" "}
                        to create a free API key.
                      </li>
                      <li>
                        <span className="font-medium text-gray-900">
                          OpenAI:
                        </span>{" "}
                        Visit{" "}
                        <a
                          href="https://platform.openai.com/api-keys"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-primary-600 hover:text-primary-500"
                        >
                          OpenAI Platform
                        </a>{" "}
                        to create an API key (requires account with billing).
                      </li>
                    </ul>
                  </div>
                </div>

                <div className="mt-6 rounded-lg bg-blue-50 p-4">
                  <p className="text-sm text-blue-800">
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
    </div>
  );
};

export default SettingsPage;
