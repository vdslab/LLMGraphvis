import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AnalysisFeedback from '../components/chat/AnalysisFeedback';
import api from '../services/api';

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
  getApiErrorMessage: (error) => error.message,
}));

const message = { id: 12, content: 'Analysis complete.' };

describe('AnalysisFeedback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: [] });
    api.put.mockResolvedValue({ data: {} });
  });

  it('records a specific source of confusion on the response', async () => {
    render(<AnalysisFeedback chatId={3} message={message} />);
    fireEvent.click(screen.getByRole('button', { name: 'Tell us' }));
    fireEvent.change(screen.getByLabelText('Which part?'), { target: { value: 'result' } });
    fireEvent.change(screen.getByPlaceholderText('What confused you? (optional)'), {
      target: { value: 'What does the score mean?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      '/chat/3/messages/12/feedback',
      { clarity: 'unclear', area: 'result', detail: 'What does the score mean?' },
    ));
    expect(await screen.findByRole('status')).toHaveTextContent('Saved');
  });

  it('restores the saved answer after reloading the conversation', async () => {
    api.get.mockResolvedValue({ data: [{ message_id: 12, clarity: 'clear', area: null, detail: null }] });
    render(<AnalysisFeedback chatId={3} message={message} />);
    expect(await screen.findByRole('status')).toHaveTextContent('Saved');
    expect(screen.getByRole('button', { name: 'Everything clear' })).toHaveAttribute('aria-pressed', 'true');
  });
});
