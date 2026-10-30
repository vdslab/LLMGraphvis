import { describe, expect, it } from 'vitest';
import { latestInteraction } from '../utils/chatInteraction';

const execution = {
  tool_name: 'offer_parameter_tuning',
  result: { parameter_tuning: { id: 'panel', question: 'Spacing' } },
};

describe('restored interactions', () => {
  it.each(['assistant', 'model'])('keeps the tuning panel for a %s reply', role => {
    const interaction = latestInteraction([{ role, tool_executions: [execution] }]);
    expect(interaction).toEqual({ kind: 'tuning', data: execution.result.parameter_tuning });
  });

  it('does not restore an old panel after a newer received user message', () => {
    expect(latestInteraction([
      { role: 'model', tool_executions: [execution] },
      { role: 'user', content: 'new task' },
    ])).toBeNull();
  });
});
