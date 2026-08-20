import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChatInterface from '../components/ChatInterface';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

vi.mock('../stores/chatStore');
vi.mock('../stores/networkStore');
vi.mock('react-markdown', () => ({ default: ({ children }) => <div>{children}</div> }));
vi.mock('remark-gfm', () => ({ default: () => {} }));
vi.mock('remark-breaks', () => ({ default: () => {} }));

const PLACEHOLDER = 'Ask about this network…';

describe('ChatInterface', () => {
    const mockSendMessage = vi.fn();

    // The panel's children (ModelSelector, UsageBadge) read the store with
    // selectors, so the mock has to honour one rather than return the state
    // object for every call.
    const setStore = (overrides = {}) => {
        const state = {
            messages: [],
            sendMessage: mockSendMessage,
            retryMessage: vi.fn(),
            isLoading: false,
            thinkingMessage: null,
            progressSteps: [],
            runningTool: null,
            uploadNetwork: vi.fn(),
            chatId: 1,
            llmProviders: [],
            fetchLlmProviders: vi.fn(),
            updateChatSettings: vi.fn(),
            chatUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0 },
            currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0 },
            ...overrides,
        };
        useChatStore.mockImplementation((selector) =>
            typeof selector === 'function' ? selector(state) : state
        );
    };

    beforeEach(() => {
        vi.clearAllMocks();
        setStore();
        useNetworkStore.mockImplementation((selector) => {
            const state = { nodes: [] };
            return typeof selector === 'function' ? selector(state) : state;
        });
    });

    it('renders input area', () => {
        render(<ChatInterface />);
        expect(screen.getByPlaceholderText(PLACEHOLDER)).toBeInTheDocument();
    });

    it('updates input value on change', () => {
        render(<ChatInterface />);
        const input = screen.getByPlaceholderText(PLACEHOLDER);
        fireEvent.change(input, { target: { value: 'Hello' } });
        expect(input.value).toBe('Hello');
    });

    it('sends message on Enter without Shift', async () => {
        render(<ChatInterface />);
        const input = screen.getByPlaceholderText(PLACEHOLDER);

        fireEvent.change(input, { target: { value: 'Hello' } });
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: false, code: 'Enter' });

        expect(mockSendMessage).toHaveBeenCalledWith('Hello');
        await waitFor(() => {
            expect(input.value).toBe('');
        });
    });

    it('does NOT send message on Shift+Enter', () => {
        render(<ChatInterface />);
        const input = screen.getByPlaceholderText(PLACEHOLDER);

        fireEvent.change(input, { target: { value: 'Line 1' } });
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: true, code: 'Enter' });

        expect(mockSendMessage).not.toHaveBeenCalled();
    });

    it('accepts a message while a turn is still running', () => {
        // The backend answers 202 and streams the rest, so there is no reason to
        // take the keyboard away until it finishes.
        setStore({ isLoading: true });
        render(<ChatInterface />);

        const input = screen.getByPlaceholderText('Add another message…');
        expect(input).not.toBeDisabled();

        fireEvent.change(input, { target: { value: 'and colour by community' } });
        fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

        expect(mockSendMessage).toHaveBeenCalledWith('and colour by community');
    });

    it('says how many messages are waiting for the current turn', () => {
        setStore({
            isLoading: true,
            messages: [{ id: 'l1', role: 'user', content: 'later', status: 'queued' }],
        });
        render(<ChatInterface />);

        expect(screen.getByText(/1 message waiting/)).toBeInTheDocument();
    });

    it('shows backend progress as steps, not as thinking', () => {
        setStore({
            isLoading: true,
            progressSteps: [{ label: 'Importing GraphML data', status: 'running' }],
        });
        render(<ChatInterface />);

        expect(screen.getByText('Importing GraphML data')).toBeInTheDocument();
        expect(screen.queryByText('Thinking')).not.toBeInTheDocument();
    });

    it('labels the model reasoning stream as Thinking', () => {
        setStore({ isLoading: true, thinkingMessage: 'I should compute centrality' });
        render(<ChatInterface />);

        expect(screen.getByText('Thinking')).toBeInTheDocument();
    });

    it('folds thought markup attached to a tool execution', () => {
        setStore({
            messages: [{
                id: 1,
                role: 'assistant',
                content: '<tool_execution_marker index="0"/>The result is ready.',
                tool_executions: [{
                    tool_name: 'analysis_degree_centrality',
                    status: 'completed',
                    thought: '<thought>I should compute centrality</thought>',
                }],
            }],
        });
        render(<ChatInterface />);

        expect(screen.getByTitle('analysis_degree_centrality')).toBeInTheDocument();
        const toggle = screen.getByRole('button', { name: 'Thinking' });
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(screen.queryByText('I should compute centrality')).not.toBeInTheDocument();
        expect(screen.queryByText(/<\/?thought>/)).not.toBeInTheDocument();

        fireEvent.click(toggle);
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByText('I should compute centrality')).toBeInTheDocument();
    });
});
