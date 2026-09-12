import { useEffect, useState } from 'react';
import api, { getApiErrorMessage } from '../../services/api';
import { useChatStore } from '../../stores/chatStore';
import { useNetworkStore } from '../../stores/networkStore';

const formatAnswer = (value) => Array.isArray(value) ? value.map(formatAnswer).join(', ')
  : value && typeof value === 'object' ? `Other: ${value.other}` : String(value ?? '');

/** A persisted question. Server state, never initial UI values, proves submission. */
export default function InputRequest({ request }) {
  const { chatId, isLoading, messages, sendMessage } = useChatStore();
  const networkId = useNetworkStore((state) => state.networkId);
  const [current, setCurrent] = useState(request);
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [values, setValues] = useState(() => Object.fromEntries(
    request.fields.map((field) => [field.id,
      field.kind === 'multiselect' ? [] : field.kind === 'slider' ? field.minimum : '',
    ]),
  ));

  useEffect(() => {
    let active = true;
    setVerified(false);
    api.get(`/chat/${request.chat_id}/inputs/${request.id}`).then(({ data }) => {
      if (active) { setCurrent(data); setVerified(true); setError(''); }
    }).catch((failure) => {
      if (active) setError(getApiErrorMessage(failure));
    });
    return () => { active = false; };
  }, [request.id, request.chat_id, isLoading, messages.length, networkId]);

  const disabled = !verified || current.status !== 'pending' || isLoading || sending
    || String(chatId) !== String(request.chat_id);
  const update = (id, value) => setValues((old) => ({ ...old, [id]: value }));
  const submit = async (event) => {
    event.preventDefault();
    if (disabled) return;
    setSending(true);
    setError('');
    const content = [current.question, ...current.fields.map((field) =>
      `${field.label}: ${formatAnswer(values[field.id])}`,
    )].join('\n');
    const accepted = await sendMessage(content, {
      input_request_id: current.id, input_values: values,
    });
    if (accepted) setCurrent((old) => ({ ...old, status: 'answered', answer: values }));
    else setError('Could not submit. Check your input and try again.');
    setSending(false);
  };

  return (
    <form className="input-request" onSubmit={submit}>
      <p className="input-request__question">{current.question}</p>
      {current.status === 'pending' ? <>
        <fieldset disabled={disabled}>
          {current.fields.map((field) => {
            const id = `input-${request.id}-${field.id}`;
            const value = values[field.id];
            const allowOther = field.allow_other !== false;
            const isOther = value && typeof value === 'object' && !Array.isArray(value);
            let otherKey = '__other__';
            while (field.options?.includes(otherKey)) otherKey += '_';
            const otherInput = (text, onChange) => <div className="input-request__field">
              <label htmlFor={`${id}-other`}>{field.label}: Other details</label>
              <textarea id={`${id}-other`} required maxLength={4000} value={text}
                placeholder="Enter what you would like to do"
                onChange={(event) => onChange(event.target.value)} />
            </div>;
            if (field.kind === 'multiselect') return (
              <fieldset key={field.id} className="input-request__choices">
                <legend>{field.label}</legend>
                {field.options.map((option) => <label key={option}>
                  <input type="checkbox" checked={values[field.id].includes(option)}
                    onChange={(event) => update(field.id, event.target.checked
                      ? [...values[field.id], option] : values[field.id].filter((v) => v !== option))} />
                  {option}
                </label>)}
                {allowOther && <>
                  <label>
                    <input type="checkbox" checked={value.some((item) => typeof item === 'object')}
                      onChange={(event) => update(field.id, event.target.checked
                        ? [...value, { other: '' }] : value.filter((item) => typeof item !== 'object'))} />
                    Other (free text)
                  </label>
                  {value.some((item) => typeof item === 'object') && otherInput(
                    value.find((item) => typeof item === 'object').other,
                    (text) => update(field.id, value.map((item) => typeof item === 'object' ? { other: text } : item)),
                  )}
                </>}
              </fieldset>
            );
            return <div className="input-request__field" key={field.id}>
              <label htmlFor={id}>{field.label}</label>
              {field.kind === 'select' ? (
                <>
                  <select id={id} required value={isOther ? otherKey : value}
                    onChange={(event) => update(field.id, event.target.value === otherKey
                      ? { other: '' } : event.target.value)}>
                    <option value="">Select an option</option>
                    {field.options.map((option) => <option key={option}>{option}</option>)}
                    {allowOther && <option value={otherKey}>Other (free text)</option>}
                  </select>
                  {isOther && otherInput(value.other, (text) => update(field.id, { other: text }))}
                </>
              ) : (
                <input id={id} required type={field.kind === 'slider' ? 'range' : field.kind === 'number' ? 'number' : 'text'}
                  min={field.minimum ?? undefined} max={field.maximum ?? undefined}
                  step={field.step ?? (field.kind === 'text' ? undefined : 'any')}
                  value={values[field.id]}
                  onChange={(event) => update(field.id,
                    field.kind === 'text' || event.target.value === '' ? event.target.value : Number(event.target.value))} />
              )}
              {field.kind === 'slider' && <output htmlFor={id}>{values[field.id]}</output>}
            </div>;
          })}
          <button type="submit">{sending ? 'Sending…' : 'Continue'}</button>
        </fieldset>
        <p className="input-request__hint">You can also reply in the chat.</p>
      </> : <p className="input-request__hint">
        {current.status === 'answered' ? 'Answered' : 'This question is no longer available for the current analysis.'}
        {current.answer && <span> {Object.values(current.answer).map(formatAnswer).join(' / ')}</span>}
      </p>}
      {error && <p role="alert" className="input-request__error">{error}</p>}
    </form>
  );
}
