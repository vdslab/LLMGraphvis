import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import ParameterTuning from '../components/chat/ParameterTuning';
import api from '../services/api';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getApiErrorMessage: (e) => e.message,
}));
vi.mock('../stores/chatStore');
vi.mock('../stores/networkStore');

const RES = 'analysis_louvain_communities.resolution';
const SIZE = 'visualization_set_node_size.max_size';

const tuning = {
  id: 'tuning-1',
  chat_id: 1,
  status: 'active',
  question: 'コミュニティの粒度',
  steps: [
    { tool: 'analysis_louvain_communities', arguments: {} },
    { tool: 'visualization_set_node_size', arguments: {} },
  ],
  fields: [
    {
      id: RES, tool: 'analysis_louvain_communities', argument: 'resolution', kind: 'slider',
      minimum: 0.2, maximum: 3, step: 0.1, description: 'Below 1 favors larger communities.',
      rationale: '密度が高いので少し細かめが見やすい', low_label: '大きなまとまり', high_label: '細かく分ける',
    },
    {
      id: SIZE, tool: 'visualization_set_node_size', argument: 'max_size', kind: 'slider',
      minimum: 10, maximum: 200, step: 10,
    },
  ],
  values: { [RES]: 1.0, [SIZE]: 50 },
  initial_values: { [RES]: 1.0, [SIZE]: 50 },
  suggested_values: { [RES]: 1.5, [SIZE]: 50 },
  history: [],
  last_result: null,
};

let sendMessage;
let setNetworkData;
let chatState;
beforeEach(() => {
  vi.clearAllMocks();
  sendMessage = vi.fn().mockResolvedValue(true);
  setNetworkData = vi.fn();
  chatState = { chatId: 1, isLoading: false, messages: [], sendMessage };
  useChatStore.mockImplementation(() => chatState);
  useNetworkStore.mockImplementation((selector) => selector({ networkId: 1, setNetworkData }));
  api.get.mockResolvedValue({ data: tuning });
});

const applyButton = () => screen.getByRole('button', { name: '適用' });

describe('ParameterTuning', () => {
  it('waits for the live state, then shows parameter names, ranges and direction', async () => {
    render(<ParameterTuning tuning={tuning} />);
    expect(applyButton()).toBeDisabled();
    await waitFor(() => expect(screen.getByLabelText('resolution')).toBeEnabled());
    expect(screen.getAllByText('analysis_louvain_communities').length).toBeGreaterThan(0);
    expect(screen.getByText('Below 1 favors larger communities.')).toBeInTheDocument();
    expect(screen.getByText('← 大きなまとまり')).toBeInTheDocument();
    expect(screen.getByText('細かく分ける →')).toBeInTheDocument();
    expect(screen.getByText(/範囲 0.2–3.0/)).toBeInTheDocument();
  });

  it('starts at the suggestion, marks current and suggested, and does not apply it', async () => {
    render(<ParameterTuning tuning={tuning} />);
    await waitFor(() => expect(screen.getByLabelText('resolution')).toBeEnabled());
    expect(screen.getByLabelText('resolution')).toHaveValue('1.5');
    expect(screen.getByTitle('現在 1.0')).toBeInTheDocument();
    expect(screen.getByTitle('推奨 1.5')).toBeInTheDocument();
    expect(screen.getByText('密度が高いので少し細かめが見やすい')).toBeInTheDocument();
    expect(screen.getByText('未適用')).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('applies several changed fields in one request and follows the result', async () => {
    const applied = { ...tuning, values: { [RES]: 2.0, [SIZE]: 120 } };
    const visualization = { nodes: [], links: [] };
    api.post.mockResolvedValue({ data: { tuning: applied, visualization, changes: [], steps: [] } });
    render(<ParameterTuning tuning={tuning} />);
    await waitFor(() => expect(screen.getByLabelText('resolution')).toBeEnabled());

    fireEvent.change(screen.getByLabelText('resolution'), { target: { value: '2.0' } });
    fireEvent.change(screen.getByLabelText('max_size'), { target: { value: '120' } });
    fireEvent.click(applyButton());

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith(
      '/chat/1/tunings/tuning-1/apply', { values: { [RES]: 2.0, [SIZE]: 120 } },
    );
    await waitFor(() => expect(setNetworkData).toHaveBeenCalledWith(visualization));
    expect(screen.queryByText('未適用')).not.toBeInTheDocument();
  });

  it('sets the suggestion without calling the server', async () => {
    render(<ParameterTuning tuning={tuning} />);
    await waitFor(() => expect(screen.getByLabelText('resolution')).toBeEnabled());
    fireEvent.change(screen.getByLabelText('resolution'), { target: { value: '0.5' } });
    fireEvent.click(screen.getByRole('button', { name: '推奨値にセット' }));
    expect(screen.getByLabelText('resolution')).toHaveValue('1.5');
    expect(api.post).not.toHaveBeenCalled();
  });

  it('confirms only applied values and hands them to the agent', async () => {
    const applied = { ...tuning, suggested_values: tuning.values };
    api.get.mockResolvedValue({ data: applied });
    render(<ParameterTuning tuning={applied} />);
    const confirm = await screen.findByRole('button', { name: 'この値で決定' });
    await waitFor(() => expect(confirm).toBeEnabled());
    fireEvent.change(screen.getByLabelText('resolution'), { target: { value: '2.0' } });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText('resolution'), { target: { value: '1.0' } });
    fireEvent.click(confirm);
    await waitFor(() => expect(sendMessage).toHaveBeenCalledWith(
      'この値で決定', { parameter_tuning_id: 'tuning-1' },
    ));
    expect(await screen.findByText('決定済み')).toBeInTheDocument();
  });

  it('follows values the agent applied from words', async () => {
    const { rerender } = render(<ParameterTuning tuning={tuning} />);
    await waitFor(() => expect(screen.getByLabelText('resolution')).toHaveValue('1.5'));

    api.get.mockResolvedValue({
      data: {
        ...tuning,
        values: { [RES]: 1.3, [SIZE]: 50 },
        history: [{
          source: 'agent', at: '2026-09-17T00:00:00Z', summary: '',
          changes: [{ param: RES, before: 1.0, after: 1.3 }],
        }],
      },
    });
    chatState = { ...chatState, messages: [{ id: 1 }] };
    await act(async () => { rerender(<ParameterTuning tuning={tuning} />); });

    await waitFor(() => expect(screen.getByLabelText('resolution')).toHaveValue('1.3'));
    const history = screen.getByText('変更履歴（1）').closest('details');
    expect(within(history).getByText('エージェント')).toBeInTheDocument();
    expect(within(history).getByText('resolution 1 → 1.3')).toBeInTheDocument();
  });

  it('shows closed panels read-only', async () => {
    api.get.mockResolvedValue({ data: { ...tuning, status: 'expired' } });
    render(<ParameterTuning tuning={tuning} />);
    expect(await screen.findByText('現在の表示では利用できません')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText('resolution = 1.0')).toBeInTheDocument();
  });

  it('uses English chrome for an English panel', async () => {
    const english = {
      ...tuning,
      question: 'Community granularity',
      fields: tuning.fields.map((field) => ({
        ...field, rationale: undefined, low_label: 'larger groups', high_label: 'finer groups',
      })),
    };
    api.get.mockResolvedValue({ data: english });
    render(<ParameterTuning tuning={english} />);
    expect(await screen.findByRole('button', { name: 'Apply' })).toBeInTheDocument();
    expect(screen.queryByText('適用')).not.toBeInTheDocument();
  });
});
