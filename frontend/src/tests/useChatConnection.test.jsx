import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useChatConnection } from '../hooks/useChatConnection';
import { useChatStore } from '../stores/chatStore';

// Mirrors how EventSource dispatches: a named server event goes to its
// listeners, and one named `error` would also reach onerror.
class FakeEventSource {
  static last = null;
  constructor(url) {
    this.url = url;
    this.listeners = {};
    FakeEventSource.last = this;
  }
  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }
  dispatch(type, data) {
    const event = { type, data: JSON.stringify(data) };
    (this.listeners[type] || []).forEach((fn) => fn(event));
    if (type === 'error' && this.onerror) this.onerror(event);
  }
  close() {
    this.readyState = 2;
  }
}
FakeEventSource.CLOSED = 2;

describe('useChatConnection', () => {
  beforeEach(() => {
    vi.stubGlobal('EventSource', FakeEventSource);
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'log').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('ends the turn on a backend error without reporting a lost connection', () => {
    const endTurn = vi.fn();
    const refreshUsage = vi.fn();
    useChatStore.setState({ endTurn, refreshUsage });

    const { result } = renderHook(() => useChatConnection('1', true));
    const es = FakeEventSource.last;
    act(() => es.onopen());
    act(() => es.dispatch('agent_error', 'Connection error.'));

    expect(endTurn).toHaveBeenCalledTimes(1);
    expect(refreshUsage).toHaveBeenCalled();
    expect(result.current.isConnected).toBe(true);
    expect(result.current.sseError).toBeNull();
  });

  it('resyncs messages when the stream reopens after a loss', () => {
    const resyncMessages = vi.fn().mockResolvedValue();
    useChatStore.setState({ resyncMessages });

    renderHook(() => useChatConnection('1', true));
    const es = FakeEventSource.last;
    act(() => es.onopen());
    expect(resyncMessages).not.toHaveBeenCalled();

    act(() => es.onerror({}));
    act(() => es.onopen());
    expect(resyncMessages).toHaveBeenCalledTimes(1);
  });

  it('reopens a closed stream when the tab comes back into view', () => {
    useChatStore.setState({ resyncMessages: vi.fn().mockResolvedValue() });
    renderHook(() => useChatConnection('1', true));
    const first = FakeEventSource.last;
    first.close();

    act(() => document.dispatchEvent(new Event('visibilitychange')));

    expect(FakeEventSource.last).not.toBe(first);
  });
});
