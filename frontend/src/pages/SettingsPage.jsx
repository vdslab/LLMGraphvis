import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';
import { useSettingsStore } from '../stores/settingsStore';
import { defaultModelLabel } from '../utils/llmModels';
import UsageSummary from '../components/usage/UsageSummary';
import { getApiErrorMessage, getUserUsage } from '../services/api';
import { formatCost, formatTokenCount, formatTotalCost } from '../utils/usageFormat';
import '../components/usage/usage.css';
import './SettingsPage.css';

const TABS = [
  { id: 'account', label: 'Account' },
  { id: 'llm', label: 'LLM' },
  { id: 'usage', label: 'Usage' },
];

const MIN_PASSWORD_LENGTH = 8;

// --- Account ---------------------------------------------------------------

const AccountTab = () => {
  const user = useAuthStore((state) => state.user);
  const changePassword = useSettingsStore((state) => state.changePassword);
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [status, setStatus] = useState({ kind: null, message: '' });
  const [saving, setSaving] = useState(false);

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  const mismatch = form.confirm && form.next !== form.confirm;
  const tooShort = form.next && form.next.length < MIN_PASSWORD_LENGTH;
  const canSubmit = form.current && form.next && form.confirm && !mismatch && !tooShort && !saving;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setStatus({ kind: null, message: '' });
    try {
      await changePassword(form.current, form.next);
      setForm({ current: '', next: '', confirm: '' });
      setStatus({
        kind: 'success',
        message: 'Password changed. Other devices have been signed out.',
      });
    } catch (error) {
      setStatus({ kind: 'error', message: getApiErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-section" aria-labelledby="settings-password">
      <div className="settings-field-row">
        <span className="settings-label">Username</span>
        <span>{user?.username}</span>
      </div>

      <h3 id="settings-password" className="settings-section__title">Change password</h3>
      <form className="settings-form" onSubmit={handleSubmit}>
        <label className="settings-field">
          <span className="settings-label">Current password</span>
          <input className="input" type="password" autoComplete="current-password"
            value={form.current} onChange={update('current')} />
        </label>
        <label className="settings-field">
          <span className="settings-label">New password</span>
          <input className="input" type="password" autoComplete="new-password"
            value={form.next} onChange={update('next')} aria-invalid={Boolean(tooShort)} />
          <span className={`settings-hint${tooShort ? ' settings-hint--error' : ''}`}>
            At least {MIN_PASSWORD_LENGTH} characters.
          </span>
        </label>
        <label className="settings-field">
          <span className="settings-label">Confirm new password</span>
          <input className="input" type="password" autoComplete="new-password"
            value={form.confirm} onChange={update('confirm')} aria-invalid={Boolean(mismatch)} />
          {mismatch && <span className="settings-hint settings-hint--error">Passwords do not match.</span>}
        </label>
        {status.kind && (
          <p className={`settings-status settings-status--${status.kind}`} role="status">{status.message}</p>
        )}
        <div>
          <button className="btn btn-primary" type="submit" disabled={!canSubmit}>
            {saving ? 'Changing…' : 'Change password'}
          </button>
        </div>
      </form>
    </section>
  );
};

// --- LLM -------------------------------------------------------------------

const encodeValue = (provider, model) => `${provider}::${model}`;
const SERVER_DEFAULT = 'server-default';

const LlmTab = () => {
  const llmProviders = useChatStore((state) => state.llmProviders);
  const fetchLlmProviders = useChatStore((state) => state.fetchLlmProviders);
  const settings = useSettingsStore((state) => state.settings);
  const fetchSettings = useSettingsStore((state) => state.fetchSettings);
  const setDefaultModel = useSettingsStore((state) => state.setDefaultModel);
  const [value, setValue] = useState(SERVER_DEFAULT);
  const [status, setStatus] = useState({ kind: null, message: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchLlmProviders().catch(() => {});
    fetchSettings({ force: true }).catch(() => {});
  }, [fetchLlmProviders, fetchSettings]);

  const saved = settings?.default_provider && settings?.default_model
    ? encodeValue(settings.default_provider, settings.default_model)
    : SERVER_DEFAULT;

  useEffect(() => { setValue(saved); }, [saved]);

  const serverDefaultLabel = defaultModelLabel(llmProviders, null).replace(/^Default/, 'Server default');
  const savedIsOffered = saved === SERVER_DEFAULT || llmProviders.some((provider) =>
    provider.models.some((model) => encodeValue(provider.id, model.id) === saved));

  const handleSave = async () => {
    setSaving(true);
    setStatus({ kind: null, message: '' });
    try {
      if (value === SERVER_DEFAULT) {
        await setDefaultModel(null, null);
      } else {
        const [provider, model] = value.split('::');
        await setDefaultModel(provider, model);
      }
      setStatus({ kind: 'success', message: 'Saved. Chats without their own model now use it.' });
    } catch (error) {
      setStatus({ kind: 'error', message: getApiErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-section" aria-labelledby="settings-llm">
      <h3 id="settings-llm" className="settings-section__title">Default model</h3>
      <p className="settings-description">
        The model a chat uses unless you pick one for that chat in its header.
        A chat&apos;s own choice always wins.
      </p>
      <label className="settings-field">
        <span className="settings-label">Model</span>
        <select className="input" value={value} onChange={(e) => setValue(e.target.value)}
          disabled={llmProviders.length === 0}>
          <option value={SERVER_DEFAULT}>{serverDefaultLabel}</option>
          {!savedIsOffered && (
            <option value={saved}>{settings.default_model} (unavailable)</option>
          )}
          {llmProviders.map((provider) => (
            <optgroup key={provider.id} label={provider.label}>
              {provider.models.map((model) => (
                <option key={model.id} value={encodeValue(provider.id, model.id)}>{model.label}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      {status.kind && (
        <p className={`settings-status settings-status--${status.kind}`} role="status">{status.message}</p>
      )}
      <div>
        <button className="btn btn-primary" type="button" onClick={handleSave}
          disabled={saving || value === saved}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </section>
  );
};

// --- Usage -----------------------------------------------------------------

const PERIODS = [
  { id: '7', label: 'Last 7 days', params: { days: 7 } },
  { id: '30', label: 'Last 30 days', params: { days: 30 } },
  { id: '90', label: 'Last 90 days', params: { days: 90 } },
  { id: 'all', label: 'All time', params: { allTime: true } },
];

const METRICS = [
  { id: 'tokens', label: 'Tokens', value: (d) => d.input_tokens + d.output_tokens, format: formatTokenCount },
  { id: 'cost', label: 'Cost', value: (d) => d.estimated_cost_usd, format: formatCost },
];

const localDateKey = (date) => {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

// Every calendar day from the start of the period (or the first recorded day)
// to today, with zero-usage days filled in so bar spacing is true to time.
const fillDays = (byDay, since) => {
  const known = new Map(byDay.map((day) => [day.date, day]));
  const first = since ? new Date(since) : (byDay[0] ? new Date(`${byDay[0].date}T00:00:00`) : null);
  if (!first) return [];
  const cursor = new Date(first.getFullYear(), first.getMonth(), first.getDate());
  const today = new Date();
  const days = [];
  while (cursor <= today) {
    const key = localDateKey(cursor);
    days.push(known.get(key) || {
      date: key, input_tokens: 0, output_tokens: 0, estimated_cost_usd: 0,
      unpriced_count: 0, task_count: 0,
    });
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
};

const DailyChart = ({ days, metric }) => {
  const max = Math.max(...days.map(metric.value), 0);
  if (days.length === 0 || max === 0) {
    return <p className="settings-description">No usage in this period.</p>;
  }
  return (
    <div className="daily-chart" role="img"
      aria-label={`${metric.label} per day; exact values are in the table below.`}>
      <div className="daily-chart__plot">
        {days.map((day) => {
          const value = metric.value(day);
          return (
            <div key={day.date} className="daily-chart__slot" tabIndex={0}>
              <div className="daily-chart__bar" style={{ height: `${Math.max((value / max) * 100, value ? 2 : 0)}%` }} />
              <div className="daily-chart__tip" role="tooltip">
                <strong>{day.date}</strong>
                <span>{formatTokenCount(day.input_tokens)} in · {formatTokenCount(day.output_tokens)} out</span>
                <span>{formatTotalCost(day)} · {day.task_count} tasks</span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="daily-chart__axis">
        <span>{days[0].date}</span>
        <span>max {metric.format(max)}</span>
        <span>{days[days.length - 1].date}</span>
      </div>
    </div>
  );
};

const UsageTable = ({ caption, rows, nameOf }) => (
  <div className="usage-table-wrap">
  <table className="usage-table">
    <caption>{caption}</caption>
    <thead>
      <tr><th>Name</th><th>Input</th><th>Cached</th><th>Output</th><th>Reasoning</th><th>Requests</th><th>Est. cost</th></tr>
    </thead>
    <tbody>
      {rows.map((row) => (
        <tr key={nameOf(row).key}>
          <td>{nameOf(row).node}</td>
          <td>{row.input_tokens.toLocaleString()}</td>
          <td>{row.cached_input_tokens.toLocaleString()}</td>
          <td>{row.output_tokens.toLocaleString()}</td>
          <td>{row.reasoning_tokens.toLocaleString()}</td>
          <td>{row.request_count.toLocaleString()}</td>
          <td>{formatTotalCost(row)}</td>
        </tr>
      ))}
    </tbody>
  </table>
  </div>
);

const UsageTab = () => {
  const [period, setPeriod] = useState('30');
  const [metricId, setMetricId] = useState('tokens');
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async (periodId) => {
    setError(null);
    const { params } = PERIODS.find((p) => p.id === periodId);
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const res = await getUserUsage({ ...params, tz });
      setReport(res.data);
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  }, []);

  useEffect(() => { load(period); }, [load, period]);

  const metric = METRICS.find((m) => m.id === metricId);
  const days = useMemo(
    () => (report ? fillDays(report.by_day, report.since) : []),
    [report],
  );

  return (
    <section className="settings-section" aria-labelledby="settings-usage">
      <div className="settings-toolbar">
        <h3 id="settings-usage" className="settings-section__title">Token usage</h3>
        <select className="input settings-toolbar__select" value={period}
          onChange={(e) => setPeriod(e.target.value)} aria-label="Period">
          {PERIODS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </div>

      {error && <p className="settings-status settings-status--error">{error}</p>}
      {!report && !error && <p className="settings-description">Loading…</p>}

      {report && (
        <>
          <UsageSummary totals={report.totals} />

          <div className="settings-toolbar">
            <h4 className="settings-subtitle">Per day</h4>
            <div className="segmented" role="radiogroup" aria-label="Chart metric">
              {METRICS.map((m) => (
                <button key={m.id} type="button" role="radio" aria-checked={m.id === metricId}
                  onClick={() => setMetricId(m.id)}>{m.label}</button>
              ))}
            </div>
          </div>
          <DailyChart days={days} metric={metric} />

          {report.by_model.length > 0 && (
            <UsageTable caption="By model" rows={report.by_model}
              nameOf={(row) => ({ key: `${row.provider}/${row.model}`, node: <>{row.model}<span className="usage-table__sub">{row.provider}</span></> })} />
          )}
          {report.by_chat.length > 0 && (
            <UsageTable caption="By chat" rows={report.by_chat}
              nameOf={(row) => ({
                key: `chat-${row.chat_id}`,
                node: row.chat_id
                  ? <Link to={`/chat/${row.chat_id}`}>{row.chat_name || `Chat ${row.chat_id}`}</Link>
                  : 'Deleted chat',
              })} />
          )}
          {report.by_day.length > 0 && (
            <UsageTable caption="By day" rows={[...report.by_day].reverse()}
              nameOf={(row) => ({ key: row.date, node: row.date })} />
          )}

          <p className="usage-popover__note">
            Input includes cached tokens; output includes reasoning. Costs are estimates from list prices;
            “+” marks totals that leave out models without a known price. Usage recorded before
            this breakdown existed lacks cache-write and reasoning counts.
          </p>
        </>
      )}
    </section>
  );
};

// --- Page ------------------------------------------------------------------

const SettingsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get('tab');
  const tab = TABS.some((t) => t.id === requested) ? requested : 'account';

  return (
    <div className="settings-page">
      <h2 className="settings-page__title">Settings</h2>
      <div className="settings-tabs" role="tablist" aria-label="Settings sections">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id}
            onClick={() => setSearchParams({ tab: t.id })}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="settings-card" role="tabpanel">
        {tab === 'account' && <AccountTab />}
        {tab === 'llm' && <LlmTab />}
        {tab === 'usage' && <UsageTab />}
      </div>
    </div>
  );
};

export default SettingsPage;
