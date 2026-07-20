import { useEffect, useState } from 'react';
import { useChatStore } from '../stores/chatStore';

const DEFAULT_VALUE = 'default';
const encodeValue = (provider, model) => `${provider}::${model}`;

const ModelSelector = () => {
  const chatId = useChatStore((state) => state.chatId);
  const chatProvider = useChatStore((state) => state.chatProvider);
  const chatModel = useChatStore((state) => state.chatModel);
  const llmProviders = useChatStore((state) => state.llmProviders);
  const fetchLlmProviders = useChatStore((state) => state.fetchLlmProviders);
  const updateChatSettings = useChatStore((state) => state.updateChatSettings);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchLlmProviders();
  }, [fetchLlmProviders]);

  if (llmProviders.length === 0 || !chatId) return null;

  const value = chatProvider && chatModel ? encodeValue(chatProvider, chatModel) : DEFAULT_VALUE;

  const defaultModel = llmProviders
    .flatMap((provider) => provider.models)
    .find((model) => model.default);
  const defaultLabel = defaultModel ? `Default (${defaultModel.label})` : 'Default';

  const handleChange = async (e) => {
    const raw = e.target.value;
    setIsSaving(true);
    try {
      if (raw === DEFAULT_VALUE) {
        await updateChatSettings(chatId, { provider: null, model: null });
      } else {
        const [provider, model] = raw.split('::');
        await updateChatSettings(chatId, { provider, model });
      }
    } catch (error) {
      console.error('Failed to update chat model:', error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <select
      value={value}
      onChange={handleChange}
      disabled={isSaving}
      title="LLM provider/model used for this chat"
      style={{
        padding: '0.25rem 0.5rem',
        borderRadius: '999px',
        border: '1px solid var(--border-color)',
        backgroundColor: 'var(--background-color)',
        color: 'var(--text-secondary)',
        fontSize: '0.8rem',
        cursor: isSaving ? 'wait' : 'pointer',
        maxWidth: '160px',
        minWidth: 0,
        flexShrink: 1,
        textOverflow: 'ellipsis'
      }}
    >
      <option value={DEFAULT_VALUE}>{defaultLabel}</option>
      {llmProviders.map((provider) => (
        <optgroup key={provider.id} label={provider.label}>
          {provider.models.map((model) => (
            <option key={model.id} value={encodeValue(provider.id, model.id)}>
              {model.label}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
};

export default ModelSelector;
