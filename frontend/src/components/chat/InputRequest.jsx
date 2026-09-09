import { useEffect, useState } from 'react';
import api, { getApiErrorMessage } from '../../services/api';
import { useChatStore } from '../../stores/chatStore';
import { useNetworkStore } from '../../stores/networkStore';

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
      `${field.label}: ${Array.isArray(values[field.id]) ? values[field.id].join(', ') : values[field.id]}`,
    )].join('\n');
    const accepted = await sendMessage(content, {
      input_request_id: current.id, input_values: values,
    });
    if (accepted) setCurrent((old) => ({ ...old, status: 'answered', answer: values }));
    else setError('送信できませんでした。入力内容を確認して再送してください。');
    setSending(false);
  };

  return (
    <form className="input-request" onSubmit={submit}>
      <p className="input-request__question">{current.question}</p>
      {current.status === 'pending' ? <>
        <fieldset disabled={disabled}>
          {current.fields.map((field) => {
            const id = `input-${request.id}-${field.id}`;
            if (field.kind === 'multiselect') return (
              <fieldset key={field.id} className="input-request__choices">
                <legend>{field.label}</legend>
                {field.options.map((option) => <label key={option}>
                  <input type="checkbox" checked={values[field.id].includes(option)}
                    onChange={(event) => update(field.id, event.target.checked
                      ? [...values[field.id], option] : values[field.id].filter((v) => v !== option))} />
                  {option}
                </label>)}
              </fieldset>
            );
            return <div className="input-request__field" key={field.id}>
              <label htmlFor={id}>{field.label}</label>
              {field.kind === 'select' ? (
                <select id={id} required value={values[field.id]}
                  onChange={(event) => update(field.id, event.target.value)}>
                  <option value="">選択してください</option>
                  {field.options.map((option) => <option key={option}>{option}</option>)}
                </select>
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
          <button type="submit">{sending ? '送信中…' : 'この内容で進める'}</button>
        </fieldset>
        <p className="input-request__hint">チャットに文章で回答することもできます。</p>
      </> : <p className="input-request__hint">
        {current.status === 'answered' ? '回答済み' : 'この質問は現在の分析では使用できません。'}
        {current.answer && <span> {Object.values(current.answer).map((v) => Array.isArray(v) ? v.join(', ') : String(v)).join(' / ')}</span>}
      </p>}
      {error && <p role="alert" className="input-request__error">{error}</p>}
    </form>
  );
}
