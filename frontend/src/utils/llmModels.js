// The label of what an unpinned chat runs on: the user's default when set,
// else the server default flagged in the provider catalog (ADR 0026).
export const defaultModelLabel = (llmProviders, settings) => {
  const models = llmProviders.flatMap((provider) =>
    provider.models.map((model) => ({ ...model, provider: provider.id })),
  );
  if (settings?.default_provider && settings?.default_model) {
    const mine = models.find(
      (m) => m.provider === settings.default_provider && m.id === settings.default_model,
    );
    return `Default (${mine ? mine.label : settings.default_model})`;
  }
  const serverDefault = models.find((model) => model.default);
  return serverDefault ? `Default (${serverDefault.label})` : 'Default';
};
