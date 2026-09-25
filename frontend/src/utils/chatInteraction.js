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

export const latestInteraction = (messages) => {
  const latest = messages.at(-1);
  if (latest?.role !== 'assistant') return null;
  const executions = latest.tool_executions ?? [];
  for (let i = executions.length - 1; i >= 0; i -= 1) {
    const interaction = interactionForExecution(executions[i]);
    if (interaction) return interaction;
  }
  return null;
};
