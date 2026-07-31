import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChatStore } from '../stores/chatStore';
import * as api from '../services/api';

vi.mock('../services/api');

const state = () => useChatStore.getState();
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('chatStore sending', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useChatStore.setState({
      chatId: 1,
      messages: [],
      isLoading: false,
      thinkingMessage: null,
      progressSteps: [],
      runningTool: null,
      streamingMessageId: null,
    });
    api.processMessage.mockResolvedValue({ status: 202 });
  });

  it('shows the message before the request resolves', async () => {
    let release;
    api.processMessage.mockReturnValue(new Promise((r) => { release = r; }));

    state().sendMessage('hello');

    expect(state().messages).toHaveLength(1);
    expect(state().messages[0]).toMatchObject({ role: 'user', content: 'hello' });
    expect(state().isLoading).toBe(true);

    release({});
    await flush();
    expect(state().messages[0].status).toBe('sent');
  });

  it('queues a message sent while a turn is running instead of refusing it', async () => {
    await state().sendMessage('first');
    expect(state().isLoading).toBe(true);

    await state().sendMessage('second');

    expect(api.processMessage).toHaveBeenCalledTimes(1);
    expect(state().messages.map((m) => m.status)).toEqual(['sent', 'queued']);
  });

  it('sends the queued message when the turn ends', async () => {
    await state().sendMessage('first');
    await state().sendMessage('second');

    state().endTurn();
    await flush();

    expect(api.processMessage).toHaveBeenCalledTimes(2);
    expect(api.processMessage).toHaveBeenLastCalledWith(1, 'second');
    expect(state().messages[1].status).toBe('sent');
  });

  it('sends only one queued message per turn', async () => {
    await state().sendMessage('first');
    await state().sendMessage('second');
    await state().sendMessage('third');

    state().endTurn();
    await flush();

    expect(api.processMessage).toHaveBeenCalledTimes(2);
    expect(state().messages[2].status).toBe('queued');
  });

  it('marks a failed send and leaves the turn closed', async () => {
    api.processMessage.mockRejectedValue(new Error('offline'));

    await state().sendMessage('hello');

    expect(state().messages[0].status).toBe('failed');
    expect(state().isLoading).toBe(false);
  });

  it('resends a failed message on retry', async () => {
    api.processMessage.mockRejectedValueOnce(new Error('offline'));
    await state().sendMessage('hello');

    await state().retryMessage(state().messages[0]);

    expect(api.processMessage).toHaveBeenCalledTimes(2);
    expect(state().messages[0].status).toBe('sent');
  });

  it('clears every per-turn indicator when the turn ends', async () => {
    useChatStore.setState({
      isLoading: true,
      thinkingMessage: 'reasoning',
      progressSteps: [{ label: 'Importing', status: 'running' }],
      runningTool: { name: 'layout_spring' },
    });

    state().endTurn();

    expect(state()).toMatchObject({
      isLoading: false,
      thinkingMessage: null,
      progressSteps: [],
      runningTool: null,
    });
  });
});

describe('chatStore progress', () => {
  beforeEach(() => {
    useChatStore.setState({ progressSteps: [], isLoading: false });
  });

  it('finishes the previous step when a new one starts', () => {
    state().setProgress({ label: 'Importing', status: 'running' });
    state().setProgress({ label: 'Laying out', status: 'running' });

    expect(state().progressSteps).toEqual([
      { label: 'Importing', status: 'done' },
      { label: 'Laying out', status: 'running' },
    ]);
  });

  it('marks a step done in place rather than repeating it', () => {
    state().setProgress({ label: 'Importing', status: 'running' });
    state().setProgress({ label: 'Importing', status: 'done' });

    expect(state().progressSteps).toEqual([{ label: 'Importing', status: 'done' }]);
  });
});

describe('chatStore tool executions', () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      streamingMessageId: null,
      pendingToolExecutions: [],
      thinkingMessage: null,
    });
  });

  it('keeps a tool result that finishes before the message exists', () => {
    // The agent often calls a tool without writing any text first, so the
    // assistant message it belongs to has not been created yet.
    state().addToolExecutionToStreamingMessage({ tool_name: 'layout_spring' });
    state().appendMessageChunk('\n\n<tool_execution_marker index="0"/>\n\n');

    const message = state().messages[0];
    expect(message.tool_executions).toEqual([{ tool_name: 'layout_spring' }]);
    expect(state().pendingToolExecutions).toEqual([]);
  });

  it('appends to the message once one exists', () => {
    state().appendMessageChunk('Working on it.');
    state().addToolExecutionToStreamingMessage({ tool_name: 'layout_spring' });

    expect(state().messages[0].tool_executions).toHaveLength(1);
    expect(state().pendingToolExecutions).toEqual([]);
  });
});
