import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import UsageBadge from '../components/UsageBadge';
import { useChatStore, EMPTY_USAGE_TOTALS } from '../stores/chatStore';
import { addUsage, formatCost, formatTotalCost } from '../utils/usageFormat';
import { defaultModelLabel } from '../utils/llmModels';

const PROVIDERS = [
  {
    id: 'google',
    label: 'Google Gemini',
    models: [
      { id: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash', default: true },
      { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro', default: false },
    ],
  },
];

describe('usage formatting', () => {
  it('shows an unknown cost as unknown, not free', () => {
    expect(formatCost(null)).toBe('—');
    expect(formatCost(0.0032)).toBe('$0.0032');
    expect(formatTotalCost({ estimated_cost_usd: 1.5, unpriced_count: 1 })).toBe('$1.50+');
  });

  it('counts a live turn without a price as unpriced', () => {
    const total = addUsage(
      { input_tokens: 10, output_tokens: 1, estimated_cost_usd: 0.5 },
      { input_tokens: 5, output_tokens: 1, estimated_cost_usd: null },
    );
    expect(total.input_tokens).toBe(15);
    expect(total.unpriced_count).toBe(1);
  });

  it('labels the default with the user choice, else the server default', () => {
    expect(defaultModelLabel(PROVIDERS, null)).toBe('Default (Gemini 3.8 Flash)');
    expect(
      defaultModelLabel(PROVIDERS, { default_provider: 'google', default_model: 'gemini-2.5-pro' }),
    ).toBe('Default (Gemini 2.5 Pro)');
  });
});

describe('UsageBadge', () => {
  beforeEach(() => {
    useChatStore.setState({
      chatId: 7,
      chatUsage: {
        chatId: 7,
        totals: { ...EMPTY_USAGE_TOTALS, input_tokens: 1000, output_tokens: 200, estimated_cost_usd: 0.02, task_count: 1, request_count: 2 },
        entries: [{
          id: 1, purpose: 'agent_turn', model: 'gemini-3.8-flash', provider: 'google',
          input_tokens: 1000, output_tokens: 200, cached_input_tokens: 0, cache_write_tokens: 0,
          reasoning_tokens: 0, estimated_cost_usd: 0.02, created_at: '2026-09-29T00:00:00Z',
          calls: [{ input_tokens: 400, output_tokens: 100 }, { input_tokens: 600, output_tokens: 100 }],
        }],
      },
      currentTurnUsage: {
        input_tokens: 500, output_tokens: 100, cached_input_tokens: 0, cache_write_tokens: 0,
        reasoning_tokens: 0, estimated_cost_usd: 0.01, provider: 'google', model: 'gemini-3.8-flash',
      },
      fetchChatUsage: vi.fn().mockResolvedValue(null),
    });
  });

  it('adds the live turn to the stored total', () => {
    render(<MemoryRouter><UsageBadge /></MemoryRouter>);
    expect(screen.getByRole('button', { name: /1\.8K tokens · \$0\.03/ })).toBeInTheDocument();
  });

  it('never shows another chat\'s stored usage', () => {
    useChatStore.setState({ chatId: 8, currentTurnUsage: { ...useChatStore.getState().currentTurnUsage, input_tokens: 0, output_tokens: 0 } });
    const { container } = render(<MemoryRouter><UsageBadge /></MemoryRouter>);
    expect(container).toBeEmptyDOMElement();
  });

  it('opens a breakdown with each request of a turn', () => {
    render(<MemoryRouter><UsageBadge /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /tokens/ }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(useChatStore.getState().fetchChatUsage).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Turn/ }));
    expect(screen.getAllByRole('row')).toHaveLength(3);
  });
});
