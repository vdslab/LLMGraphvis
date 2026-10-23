export const interactionForExecution = (execution) => {
  if (execution?.tool_name === 'ask_user' && execution.result?.input_request?.id) {
    return { kind: 'choice', data: execution.result.input_request };
  }
  if (execution?.tool_name === 'offer_parameter_tuning'
      && execution.result?.parameter_tuning?.id) {
    return { kind: 'tuning', data: execution.result.parameter_tuning };
  }
  return null;
};

export const interactionKey = (interaction) => interaction
  ? `${interaction.kind}:${interaction.data.id}` : null;

// Messages the backend has not received. They are not part of the stored
// conversation, so they must not hide the question the last reply ended with.
const UNSENT = new Set(['queued', 'held', 'failed']);
export const isUnsent = (message) => UNSENT.has(message?.status);

export const latestInteraction = (messages) => {
  const latest = messages.findLast((message) => !isUnsent(message));
  if (latest?.role !== 'assistant') return null;
  const executions = latest.tool_executions ?? [];
  for (let i = executions.length - 1; i >= 0; i -= 1) {
    const interaction = interactionForExecution(executions[i]);
    if (interaction) return interaction;
  }
  return null;
};

export const looksJapanese = (text) => /[぀-ヿ一-鿿]/.test(text ?? '');
