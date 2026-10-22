import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import NetworkChatPage from '../pages/NetworkChatPage';
import { readBlobErrorBody } from '../services/api';
import * as api from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

vi.mock('../hooks/useChatConnection', () => ({
  useChatConnection: () => ({ sseError: null }),
}));
vi.mock('../components/NetworkGraph', () => ({ default: () => null }));
vi.mock('../components/ChatInterface', () => ({ default: () => null }));
vi.mock('../components/LegendPanel', () => ({ default: () => null }));

describe('readBlobErrorBody', () => {
  it('turns a JSON error Blob into the object getApiErrorMessage reads', async () => {
    const blob = new Blob([JSON.stringify({ detail: 'The network could not be exported.' })], {
      type: 'application/json',
    });

    await expect(readBlobErrorBody(blob)).resolves.toEqual({
      detail: 'The network could not be exported.',
    });
  });

  it('leaves non-Blob and non-JSON bodies alone', async () => {
    const data = { detail: 'plain' };
    expect(await readBlobErrorBody(data)).toBe(data);
    const text = new Blob(['<html>Bad Gateway</html>']);
    expect(await readBlobErrorBody(text)).toBe(text);
  });
});

describe('GraphML export', () => {
  let exportSpy;

  beforeEach(() => {
    useAuthStore.setState({ isAuthenticated: true });
    useNetworkStore.setState({ nodes: [{ id: 'a' }] });
    useChatStore.setState({
      fetchChat: vi.fn().mockResolvedValue(undefined),
      fetchMessages: vi.fn().mockResolvedValue(undefined),
      fetchSampleNetworks: vi.fn().mockResolvedValue(undefined),
    });
    // The page resets the network store on load; keep a node so the bar shows.
    vi.spyOn(useNetworkStore.getState(), 'reset').mockImplementation(() => {});
    exportSpy = vi.spyOn(api, 'exportNetwork');
    window.URL.createObjectURL = vi.fn(() => 'blob:export');
    window.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('downloads the file under the name the server gives', async () => {
    exportSpy.mockResolvedValue({
      data: '<graphml/>',
      headers: { 'content-disposition': 'attachment; filename=network_42.graphml' },
    });
    const clicked = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      clicked.push(this.getAttribute('download'));
    });

    render(
      <MemoryRouter initialEntries={['/chat/7']}>
        <Routes>
          <Route path="/chat/:id" element={<NetworkChatPage />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /export/i }));

    await waitFor(() => expect(clicked).toEqual(['network_42.graphml']));
    expect(exportSpy).toHaveBeenCalledWith(7);
  });
});
