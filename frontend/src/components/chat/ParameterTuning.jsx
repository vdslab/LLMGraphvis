import { useEffect, useRef, useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import clsx from 'clsx';
import api, { getApiErrorMessage } from '../../services/api';
import { useChatStore } from '../../stores/chatStore';
import { useNetworkStore } from '../../stores/networkStore';

/** Chrome only: parameter names, tools and descriptions are shown verbatim. */
const STRINGS = {
  en: {
    apply: 'Apply',
    applying: 'Applying…',
    suggest: 'Set suggested',
    reset: 'Reset to initial',
    confirm: 'Use these values',
    confirmHint: 'Apply your changes before confirming.',
    unapplied: 'not applied',
    current: 'current',
    suggested: 'suggested',
    range: 'range',
    step: 'step',
    history: (n) => `Changes (${n})`,
    agent: 'agent',
    form: 'panel',
    lastRun: 'Last run',
    hint: 'You can also adjust this in words in the chat, e.g. “a bit finer”.',
    confirmed: 'Confirmed',
    superseded: 'Replaced by a newer panel',
    expired: 'Not available for the current view',
    valueOf: (name) => `${name} value`,
  },
  ja: {
    apply: '適用',
    applying: '適用中…',
    suggest: '推奨値にセット',
    reset: '初期値に戻す',
    confirm: 'この値で決定',
    confirmHint: '変更を適用してから決定してください。',
    unapplied: '未適用',
    current: '現在',
    suggested: '推奨',
    range: '範囲',
    step: 'step',
    history: (n) => `変更履歴（${n}）`,
    agent: 'エージェント',
    form: 'パネル',
    lastRun: '直近の実行',
    hint: 'チャットで「もう少し細かく」のように言葉でも調整できます。',
    confirmed: '決定済み',
    superseded: '新しいパネルに置き換えられました',
    expired: '現在の表示では利用できません',
    valueOf: (name) => `${name} の値`,
  },
};

const JAPANESE = /[぀-ヿ一-鿿]/;

const stringsFor = (tuning) => (
  JAPANESE.test([
    tuning.question,
    ...(tuning.fields ?? []).flatMap((f) => [f.rationale, f.low_label, f.high_label]),
  ].filter(Boolean).join(' ')) ? STRINGS.ja : STRINGS.en
);

const decimals = (step) => {
  const text = String(step ?? '');
  return text.includes('.') ? text.split('.')[1].length : 0;
};

const format = (value, field) => {
  if (value === null || value === undefined) return 'auto';
  if (typeof value !== 'number' || field?.kind === 'select') return String(value);
  return field?.step ? value.toFixed(decimals(field.step)) : String(value);
};

/** Snap to the field's step grid so float noise never fails server validation. */
const snap = (raw, field) => {
  const value = Number(raw);
  if (raw === '' || Number.isNaN(value)) return raw;
  if (!field.step) return value;
  const base = field.minimum ?? 0;
  const snapped = Math.round((value - base) / field.step) * field.step + base;
  return Number(snapped.toFixed(decimals(field.step)));
};

const percent = (value, field) => {
  if (typeof value !== 'number' || field.minimum == null || field.maximum == null) return null;
  const ratio = (value - field.minimum) / (field.maximum - field.minimum);
  return `${Math.min(100, Math.max(0, ratio * 100))}%`;
};

const sameValues = (a = {}, b = {}) => Object.keys({ ...a, ...b }).every((key) => a[key] === b[key]);

/**
 * An expert tuning panel attached to a result (ADR 0016).
 *
 * Words in the chat stay the main way to tune; this panel re-runs the pipeline
 * directly and follows changes the agent made, because both update one server
 * state that is re-fetched whenever the conversation moves.
 */
export default function ParameterTuning({ tuning }) {
  const { chatId, isLoading, messages, sendMessage } = useChatStore();
  const networkId = useNetworkStore((state) => state.networkId);
  const setNetworkData = useNetworkStore((state) => state.setNetworkData);
  const [current, setCurrent] = useState(tuning);
  const [draft, setDraft] = useState(() => ({ ...tuning.values, ...tuning.suggested_values }));
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');
  const knownValues = useRef(tuning.values);
  const text = stringsFor(current);

  const adopt = (data) => {
    setCurrent(data);
    // Someone else (the agent, another tab) applied new values: follow them.
    if (!sameValues(knownValues.current, data.values)) setDraft({ ...data.values });
    knownValues.current = data.values;
  };

  useEffect(() => {
    let active = true;
    setVerified(false);
    api.get(`/chat/${tuning.chat_id}/tunings/${tuning.id}`).then(({ data }) => {
      if (active) { adopt(data); setVerified(true); setError(''); }
    }).catch((failure) => {
      if (active) setError(getApiErrorMessage(failure));
    });
    return () => { active = false; };
  }, [tuning.id, tuning.chat_id, isLoading, messages.length, networkId]);

  const fields = current.fields ?? [];
  const values = current.values ?? {};
  const dirtyIds = fields.filter((field) => draft[field.id] !== values[field.id]).map((f) => f.id);
  const disabled = !verified || current.status !== 'active' || isLoading || Boolean(busy)
    || String(chatId) !== String(tuning.chat_id);

  const apply = async (next) => {
    const changed = Object.fromEntries(
      Object.entries(next).filter(([id, value]) => value !== values[id] && value !== ''),
    );
    if (!Object.keys(changed).length) return;
    setBusy('apply');
    setError('');
    try {
      const { data } = await api.post(
        `/chat/${tuning.chat_id}/tunings/${tuning.id}/apply`, { values: changed },
      );
      knownValues.current = data.tuning.values;
      setCurrent(data.tuning);
      setDraft({ ...data.tuning.values });
      if (data.visualization) setNetworkData(data.visualization);
    } catch (failure) {
      setError(getApiErrorMessage(failure));
    } finally {
      setBusy(null);
    }
  };

  const confirm = async () => {
    setBusy('confirm');
    setError('');
    const accepted = await sendMessage(text.confirm, { parameter_tuning_id: tuning.id });
    if (accepted) setCurrent((old) => ({ ...old, status: 'confirmed' }));
    setBusy(null);
  };

  const update = (field, raw) => setDraft((old) => ({
    ...old, [field.id]: field.kind === 'select' ? raw : snap(raw, field),
  }));

  const header = (
    <header className="parameter-tuning__header">
      <SlidersHorizontal size={14} aria-hidden className="parameter-tuning__icon" />
      <h4 className="parameter-tuning__title">{current.question}</h4>
      <span className="parameter-tuning__pipeline">
        {(current.steps ?? []).map((step) => step.tool).join(' → ')}
      </span>
    </header>
  );

  if (current.status !== 'active') {
    const label = text[current.status] ?? text.expired;
    return (
      <section className="parameter-tuning parameter-tuning--closed" aria-label={current.question}>
        {header}
        <p className="parameter-tuning__closed">
          <span className="parameter-tuning__closed-badge">{label}</span>
          {fields.map((field) => (
            <code key={field.id} className="parameter-tuning__closed-value">
              {field.argument} = {format(values[field.id], field)}
            </code>
          ))}
        </p>
        {error && <p role="alert" className="parameter-tuning__error">{error}</p>}
      </section>
    );
  }

  const history = current.history ?? [];
  const suggested = current.suggested_values ?? {};
  const canSuggest = fields.some((field) => suggested[field.id] !== draft[field.id]);
  const canReset = !sameValues(values, current.initial_values);

  return (
    <section className="parameter-tuning" aria-label={current.question}>
      {header}
      <fieldset className="parameter-tuning__fields" disabled={disabled}>
        {fields.map((field) => {
          const id = `tuning-${tuning.id}-${field.id}`;
          const value = draft[field.id];
          const currentAt = percent(values[field.id], field);
          const suggestedAt = percent(suggested[field.id], field);
          return (
            <div key={field.id} className={clsx('parameter-tuning__field', dirtyIds.includes(field.id) && 'is-dirty')}>
              <div className="parameter-tuning__field-head">
                <label htmlFor={id} className="parameter-tuning__argument">{field.argument}</label>
                <span className="parameter-tuning__tool">{field.tool}</span>
                {dirtyIds.includes(field.id) && (
                  <span className="parameter-tuning__badge">{text.unapplied}</span>
                )}
              </div>
              {field.description && (
                <p className="parameter-tuning__description">{field.description}</p>
              )}

              {field.kind === 'select' ? (
                <select id={id} className="parameter-tuning__select" value={value ?? ''}
                  onChange={(event) => update(field, event.target.value)}>
                  {field.options.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              ) : (
                <div className="parameter-tuning__control">
                  {field.kind === 'slider' && (
                    <>
                      <div className="parameter-tuning__track">
                        <input id={id} type="range" min={field.minimum} max={field.maximum}
                          step={field.step ?? 'any'} value={value ?? field.minimum}
                          onChange={(event) => update(field, event.target.value)} />
                        {currentAt && (
                          <span className="parameter-tuning__marker parameter-tuning__marker--current"
                            style={{ left: currentAt }} title={`${text.current} ${format(values[field.id], field)}`} />
                        )}
                        {suggestedAt && suggested[field.id] !== values[field.id] && (
                          <span className="parameter-tuning__marker parameter-tuning__marker--suggested"
                            style={{ left: suggestedAt }} title={`${text.suggested} ${format(suggested[field.id], field)}`} />
                        )}
                      </div>
                    </>
                  )}
                  <input
                    id={field.kind === 'slider' ? undefined : id}
                    aria-label={field.kind === 'slider' ? text.valueOf(field.argument) : undefined}
                    type="number" className="parameter-tuning__number"
                    min={field.minimum ?? undefined} max={field.maximum ?? undefined}
                    step={field.step ?? 'any'} value={value ?? ''}
                    onChange={(event) => update(field, event.target.value)}
                  />
                </div>
              )}

              {field.kind === 'slider' && (field.low_label || field.high_label) && (
                <div className="parameter-tuning__ends" aria-hidden="true">
                  <span>{field.low_label && `← ${field.low_label}`}</span>
                  <span>{field.high_label && `${field.high_label} →`}</span>
                </div>
              )}
              <p className="parameter-tuning__meta">
                {field.kind !== 'select' && field.minimum != null && (
                  <span>{text.range} {format(field.minimum, field)}–{format(field.maximum, field)}{field.step ? ` · ${text.step} ${field.step}` : ''}</span>
                )}
                <span>{text.current} <code>{format(values[field.id], field)}</code></span>
                {suggested[field.id] !== values[field.id] && (
                  <span className="parameter-tuning__suggested">{text.suggested} <code>{format(suggested[field.id], field)}</code></span>
                )}
              </p>
              {field.rationale && <p className="parameter-tuning__rationale">{field.rationale}</p>}
            </div>
          );
        })}

        <div className="parameter-tuning__actions">
          <button type="button" className="parameter-tuning__btn"
            disabled={!canSuggest} onClick={() => setDraft((old) => ({ ...old, ...suggested }))}>
            {text.suggest}
          </button>
          <button type="button" className="parameter-tuning__btn"
            disabled={!canReset} onClick={() => apply(current.initial_values)}>
            {text.reset}
          </button>
          <button type="button" className="parameter-tuning__btn parameter-tuning__btn--primary"
            disabled={!dirtyIds.length} onClick={() => apply(draft)}>
            {busy === 'apply' ? text.applying : text.apply}
          </button>
          <button type="button" className="parameter-tuning__btn parameter-tuning__btn--tonal"
            disabled={dirtyIds.length > 0} title={dirtyIds.length ? text.confirmHint : undefined}
            onClick={confirm}>
            {text.confirm}
          </button>
        </div>
      </fieldset>

      {current.last_result?.length > 0 && (
        <p className="parameter-tuning__last-run">
          {text.lastRun}: {current.last_result.map((step) => step.message).join(' / ')}
        </p>
      )}
      {history.length > 0 && (
        <details className="parameter-tuning__history">
          <summary>{text.history(history.length)}</summary>
          <ol>
            {history.map((entry) => (
              <li key={entry.at}>
                <span className="parameter-tuning__source">{text[entry.source] ?? entry.source}</span>
                {entry.changes.map((change) => (
                  <code key={change.param}>
                    {change.param.split('.').pop()} {format(change.before)} → {format(change.after)}
                  </code>
                ))}
              </li>
            ))}
          </ol>
        </details>
      )}
      <p className="parameter-tuning__hint">{text.hint}</p>
      {error && <p role="alert" className="parameter-tuning__error">{error}</p>}
    </section>
  );
}
