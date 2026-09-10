import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import InputRequest from '../components/chat/InputRequest';
import api from '../services/api';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

vi.mock('../services/api', () => ({ default: { get: vi.fn() }, getApiErrorMessage: (e) => e.message }));
vi.mock('../stores/chatStore');
vi.mock('../stores/networkStore');
const request = {
  id: 'question-1', chat_id: 1, status: 'pending', question: '分析条件を選択',
  fields: [
    { id: 'method', label: '分析目的', kind: 'select', options: ['経路', '中心性'] },
    { id: 'iterations', label: '反復回数', kind: 'slider', minimum: 10, maximum: 100, step: 10 },
    { id: 'metrics', label: '比較する指標', kind: 'multiselect', options: ['次数', '媒介'] },
  ],
};
let sendMessage;
beforeEach(() => {
  vi.clearAllMocks();
  sendMessage = vi.fn().mockResolvedValue(true);
  useChatStore.mockReturnValue({ chatId: 1, isLoading: false, messages: [], sendMessage });
  useNetworkStore.mockImplementation((selector) => selector({ networkId: 1 }));
  api.get.mockResolvedValue({ data: request });
});

describe('InputRequest', () => {
  it('waits for validation and submits only after an explicit click', async () => {
    render(<InputRequest request={request} />);
    expect(screen.getByRole('button')).toBeDisabled();
    await waitFor(() => expect(screen.getByRole('button')).toBeEnabled());
    expect(sendMessage).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('分析目的'), { target: { value: '経路' } });
    fireEvent.change(screen.getByLabelText('反復回数'), { target: { value: '30' } });
    fireEvent.click(screen.getByLabelText('次数'));
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(sendMessage).toHaveBeenCalledWith(
      expect.stringContaining('反復回数: 30'),
      { input_request_id: 'question-1', input_values: { method: '経路', iterations: 30, metrics: ['次数'] } },
    ));
    expect(await screen.findByText(/回答済み/)).toBeInTheDocument();
  });

  it('does not allow answering expired requests after reload', async () => {
    api.get.mockResolvedValue({ data: { ...request, status: 'expired' } });
    render(<InputRequest request={request} />);
    expect(await screen.findByText(/現在の分析では使用できません/)).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows a recoverable error when validation cannot be loaded', async () => {
    api.get.mockRejectedValue(new Error('offline'));
    render(<InputRequest request={request} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('offline');
    expect(screen.getByRole('button')).toBeDisabled();
  });
});

it('offers three candidates plus Other and sends custom text explicitly', async () => {
  const form = { ...request, fields: [
    { id: 'goal', label: '分析目的', kind: 'select', options: ['属性', '中心性', 'コミュニティ'] },
  ] };
  api.get.mockResolvedValue({ data: form });
  render(<InputRequest request={form} />);
  await waitFor(() => expect(screen.getByRole('button')).toBeEnabled());
  expect(screen.getAllByRole('option')).toHaveLength(5); // placeholder + three + Other
  fireEvent.change(screen.getByLabelText('分析目的'), { target: { value: '__other__' } });
  const custom = screen.getByLabelText('分析目的：その他の内容');
  expect(custom).toBeRequired();
  fireEvent.click(screen.getByRole('button'));
  expect(sendMessage).not.toHaveBeenCalled();
  fireEvent.change(custom, { target: { value: '二つのクラブの橋渡しを比較' } });
  fireEvent.click(screen.getByRole('button'));
  await waitFor(() => expect(sendMessage).toHaveBeenCalledWith(
    expect.stringContaining('その他: 二つのクラブの橋渡しを比較'),
    { input_request_id: 'question-1', input_values: { goal: { other: '二つのクラブの橋渡しを比較' } } },
  ));
  expect(await screen.findByText(/回答済み/)).toHaveTextContent('二つのクラブの橋渡しを比較');
});

it('discards custom input when switching back to a candidate', async () => {
  const form = { ...request, fields: [request.fields[0]] };
  api.get.mockResolvedValue({ data: form });
  render(<InputRequest request={form} />);
  await waitFor(() => expect(screen.getByRole('button')).toBeEnabled());
  fireEvent.change(screen.getByLabelText('分析目的'), { target: { value: '__other__' } });
  fireEvent.change(screen.getByLabelText('分析目的：その他の内容'), { target: { value: '使わない文章' } });
  fireEvent.change(screen.getByLabelText('分析目的'), { target: { value: '経路' } });
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button'));
  await waitFor(() => expect(sendMessage).toHaveBeenCalledWith(
    expect.not.stringContaining('使わない文章'),
    { input_request_id: 'question-1', input_values: { method: '経路' } },
  ));
});

it('renders a persisted custom answer after reload', async () => {
  api.get.mockResolvedValue({ data: { ...request, status: 'answered', answer: { method: { other: 'club別の比較' } } } });
  render(<InputRequest request={request} />);
  expect(await screen.findByText(/回答済み/)).toHaveTextContent('その他: club別の比較');
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
