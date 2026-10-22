import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import ChatMessage from '../components/chat/ChatMessage';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

vi.mock('../stores/chatStore');
vi.mock('../stores/networkStore');
vi.mock('react-markdown', () => ({ default: ({ children }) => <div>{children}</div> }));
vi.mock('remark-gfm', () => ({ default: () => {} }));
vi.mock('remark-breaks', () => ({ default: () => {} }));

describe('ChatMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useChatStore.mockReturnValue({ chatId: 1, isLoading: false, messages: [], sendMessage: vi.fn() });
    useNetworkStore.mockImplementation((selector) => selector({ networkId: 1 }));
  });

  it('suppresses failed ask_user when a later ask_user succeeded in the same message', () => {
    const message = {
      role: 'model',
      content: '::tool-execution{index="0"}\n\nExplanation\n\n::tool-execution{index="1"}',
      tool_executions: [
        {
          tool_name: 'ask_user',
          status: 'failed',
          error: '1 validation error for InputForm',
        },
        {
          tool_name: 'ask_user',
          status: 'completed',
          result: {
            input_request: {
              id: 'req-1',
              chat_id: 1,
              status: 'pending',
              question: 'Select a view',
              fields: [
                {
                  id: 'goal',
                  label: 'Goal',
                  kind: 'select',
                  options: ['Opt 1', 'Opt 2'],
                },
              ],
            },
          },
        },
      ],
    };

    render(<ChatMessage message={message} />);

    // The validation error from the failed ask_user must be suppressed
    expect(screen.queryByText(/1 validation error for InputForm/i)).not.toBeInTheDocument();
    // The successful InputRequest should be present
    expect(screen.getByText('Select a view')).toBeInTheDocument();
  });

  it('renders failed tool errors when not a retried ask_user', () => {
    const message = {
      role: 'model',
      content: '::tool-execution{index="0"}',
      tool_executions: [
        {
          tool_name: 'analysis_pagerank',
          status: 'failed',
          error: 'Graph is disconnected',
        },
      ],
    };

    render(<ChatMessage message={message} />);
    expect(screen.getByText('Graph is disconnected')).toBeInTheDocument();
  });
});
