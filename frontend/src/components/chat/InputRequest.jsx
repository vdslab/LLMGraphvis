import { useEffect, useState } from 'react';
import clsx from 'clsx';
import api, { getApiErrorMessage } from '../../services/api';
import { useChatStore } from '../../stores/chatStore';
import { useNetworkStore } from '../../stores/networkStore';

/** Chrome the model does not write, in the two languages it writes questions in.
 *  The backend sends question, labels and options in the conversation language
 *  (see prompts.py, Language), so an English "Other (free text)" card next to
 *  Japanese options reads as a different, untranslated control. */
const STRINGS = {
  en: {
    other: 'Other (free text)',
    otherDetails: (label) => `${label}: Other details`,
    otherPlaceholder: 'Enter what you would like to do',
    otherPrefix: 'Other: ',
    sending: 'Sending…',
    submit: 'Continue',
    hint: 'You can also reply in the chat.',
    answered: 'Answered',
    expired: 'This question is no longer available for the current analysis.',
    submitFailed: 'Could not submit. Check your input and try again.',
  },
  ja: {
    other: 'その他（自由記述）',
    otherDetails: (label) => `${label}: その他の内容`,
    otherPlaceholder: 'ご希望の内容を入力してください',
    otherPrefix: 'その他: ',
    sending: '送信中…',
    submit: '決定',
    hint: 'チャットで直接返信することもできます。',
    answered: '回答済み',
    expired: 'この質問は現在の分析では利用できません。',
    submitFailed: '送信できませんでした。入力内容を確認してもう一度お試しください。',
  },
};

const JAPANESE = /[\u3040-\u30ff\u4e00-\u9fff]/;

/** Match the chrome to the language the question itself is written in. */
const stringsFor = (request) => (
  JAPANESE.test([
    request.question,
    ...(request.fields ?? []).flatMap((field) => [field.label, ...(field.options ?? [])]),
  ].join(' ')) ? STRINGS.ja : STRINGS.en
);

const formatAnswer = (value, text = STRINGS.en) => Array.isArray(value)
  ? value.map((item) => formatAnswer(item, text)).join(', ')
  : value && typeof value === 'object' ? `${text.otherPrefix}${value.other}` : String(value ?? '');

/** A persisted question. Server state, never initial UI values, proves submission. */
export default function InputRequest({ request }) {
  const { chatId, isLoading, messages, sendMessage } = useChatStore();
  const networkId = useNetworkStore((state) => state.networkId);
  const [current, setCurrent] = useState(request);
  const text = stringsFor(current);
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
    else setError(text.submitFailed);
    setSending(false);
  };

  return (
    <form className="input-request" onSubmit={submit}>
      <p className="input-request__question">{current.question}</p>
      {current.status === 'pending' ? <>
        <fieldset disabled={disabled} className="input-request__fieldset">
          {current.fields.map((field) => {
            const id = `input-${request.id}-${field.id}`;
            const value = values[field.id];
            const allowOther = field.allow_other !== false;
            const isOther = value && typeof value === 'object' && !Array.isArray(value);
            let otherKey = '__other__';
            while (field.options?.includes(otherKey)) otherKey += '_';
            const otherInput = (typed, onChange) => (
              <div className="input-request__other-field">
                <label htmlFor={`${id}-other`}>{text.otherDetails(field.label)}</label>
                <textarea
                  id={`${id}-other`}
                  required
                  maxLength={4000}
                  value={typed}
                  placeholder={text.otherPlaceholder}
                  onChange={(event) => onChange(event.target.value)}
                />
              </div>
            );

            if (field.kind === 'multiselect') {
              return (
                <fieldset key={field.id} className="input-request__choices" role="group" aria-label={field.label}>
                  <legend className="input-request__legend">{field.label}</legend>
                  <div className="input-request__card-list">
                    {field.options.map((option) => {
                      const isChecked = Array.isArray(values[field.id]) && values[field.id].includes(option);
                      return (
                        <label key={option} className={clsx('input-request__choice-card', isChecked && 'is-selected')}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(event) => update(field.id, event.target.checked
                              ? [...values[field.id], option] : values[field.id].filter((v) => v !== option))}
                          />
                          <span className="input-request__indicator input-request__indicator--checkbox" aria-hidden="true" />
                          <span className="input-request__choice-text">{option}</span>
                        </label>
                      );
                    })}
                    {allowOther && (
                      <div className="input-request__other-wrapper">
                        <label className={clsx('input-request__choice-card', isOther && 'is-selected')}>
                          <input
                            type="checkbox"
                            checked={Array.isArray(value) && value.some((item) => typeof item === 'object')}
                            onChange={(event) => update(field.id, event.target.checked
                              ? [...value, { other: '' }] : value.filter((item) => typeof item !== 'object'))}
                          />
                          <span className="input-request__indicator input-request__indicator--checkbox" aria-hidden="true" />
                          <span className="input-request__choice-text">{text.other}</span>
                        </label>
                        {Array.isArray(value) && value.some((item) => typeof item === 'object') && otherInput(
                          value.find((item) => typeof item === 'object').other,
                          (text) => update(field.id, value.map((item) => typeof item === 'object' ? { other: text } : item)),
                        )}
                      </div>
                    )}
                  </div>
                </fieldset>
              );
            }

            if (field.kind === 'select') {
              return (
                <fieldset key={field.id} className="input-request__choices" role="radiogroup" aria-label={field.label}>
                  <legend className="input-request__legend">{field.label}</legend>
                  <div className="input-request__card-list">
                    {field.options.map((option) => {
                      const isSelected = value === option;
                      return (
                        <label key={option} className={clsx('input-request__choice-card', isSelected && 'is-selected')}>
                          <input
                            type="radio"
                            name={id}
                            value={option}
                            checked={isSelected}
                            required={!value}
                            onChange={() => update(field.id, option)}
                          />
                          <span className="input-request__indicator input-request__indicator--radio" aria-hidden="true" />
                          <span className="input-request__choice-text">{option}</span>
                        </label>
                      );
                    })}
                    {allowOther && (
                      <div className="input-request__other-wrapper">
                        <label className={clsx('input-request__choice-card', isOther && 'is-selected')}>
                          <input
                            type="radio"
                            name={id}
                            value={otherKey}
                            checked={isOther}
                            required={!value}
                            onChange={() => update(field.id, { other: '' })}
                          />
                          <span className="input-request__indicator input-request__indicator--radio" aria-hidden="true" />
                          <span className="input-request__choice-text">{text.other}</span>
                        </label>
                        {isOther && otherInput(value.other, (text) => update(field.id, { other: text }))}
                      </div>
                    )}
                  </div>
                </fieldset>
              );
            }

            return (
              <div className="input-request__field" key={field.id}>
                <label htmlFor={id}>{field.label}</label>
                <div className="input-request__input-wrapper">
                  <input
                    id={id}
                    required
                    type={field.kind === 'slider' ? 'range' : field.kind === 'number' ? 'number' : 'text'}
                    min={field.minimum ?? undefined}
                    max={field.maximum ?? undefined}
                    step={field.step ?? (field.kind === 'text' ? undefined : 'any')}
                    value={values[field.id]}
                    onChange={(event) => update(field.id,
                      field.kind === 'text' || event.target.value === '' ? event.target.value : Number(event.target.value))}
                  />
                  {field.kind === 'slider' && <output htmlFor={id} className="input-request__slider-value">{values[field.id]}</output>}
                </div>
              </div>
            );
          })}
          <div className="input-request__actions">
            <button type="submit" className="input-request__submit-btn">
              {sending ? text.sending : text.submit}
            </button>
          </div>
        </fieldset>
        <p className="input-request__hint">{text.hint}</p>
      </> : (
        <p className="input-request__answered">
          <span className="input-request__answered-badge">
            {current.status === 'answered' ? text.answered : text.expired}
          </span>
          {current.answer && (
            <span className="input-request__answered-text">
              {' '}{Object.values(current.answer).map((value) => formatAnswer(value, text)).join(' / ')}
            </span>
          )}
        </p>
      )}
      {error && <p role="alert" className="input-request__error">{error}</p>}
    </form>
  );
}
