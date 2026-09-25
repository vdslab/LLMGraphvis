import { useEffect, useState } from 'react';
import api, { getApiErrorMessage } from '../../services/api';
import './analysisFeedback.css';

const AREA_LABELS = {
  en: { goal: 'What was being analyzed', steps: 'What the app did', result: 'How to read the result', controls: 'How to adjust the view' },
  ja: { goal: '分析の目的', steps: 'アプリの操作', result: '結果の読み方', controls: '表示の調整方法' },
};

export default function AnalysisFeedback({ chatId, message }) {
  const japanese = /[\u3040-\u30ff\u4e00-\u9fff]/.test(message.content ?? '');
  const text = japanese ? {
    question: '今回の分析で分かりにくかった点はありますか？', clear: '特になし', unclear: '伝える',
    area: 'どの部分ですか？', placeholder: 'どこで迷ったか、具体的に教えてください（任意）',
    choose: '選択してください', submit: '送信', saved: '回答を保存しました。次の会話でも参照できます。',
  } : {
    question: 'Was any part of this analysis unclear?', clear: 'Everything clear', unclear: 'Tell us',
    area: 'Which part?', placeholder: 'What confused you? (optional)',
    choose: 'Choose an area', submit: 'Send', saved: 'Saved. The next conversation can use this feedback.',
  };
  const [mode, setMode] = useState(null);
  const [area, setArea] = useState('');
  const [detail, setDetail] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setMode(null);
    setArea('');
    setDetail('');
    setSaved(false);
    api.get(`/chat/${chatId}/feedback`).then(({ data }) => {
      if (!active) return;
      const previous = data.find((item) => item.message_id === message.id);
      if (previous) {
        setMode(previous.clarity);
        setArea(previous.area ?? '');
        setDetail(previous.detail ?? '');
        setSaved(true);
      }
    }).catch((failure) => {
      if (active) setError(getApiErrorMessage(failure));
    });
    return () => { active = false; };
  }, [chatId, message.id]);

  const submit = async (event, clarity = mode) => {
    event?.preventDefault();
    if (clarity === 'unclear' && !area && !detail.trim()) return;
    setBusy(true);
    setError('');
    try {
      await api.put(`/chat/${chatId}/messages/${message.id}/feedback`, {
        clarity, area: clarity === 'unclear' ? area || null : null,
        detail: clarity === 'unclear' ? detail.trim() || null : null,
      });
      setMode(clarity);
      setSaved(true);
    } catch (failure) {
      setError(getApiErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="analysis-feedback" aria-label={text.question}>
      <p className="analysis-feedback__question">{text.question}</p>
      <div className="analysis-feedback__options">
        <button type="button" disabled={busy} aria-pressed={mode === 'clear'}
          onClick={() => submit(null, 'clear')}>{text.clear}</button>
        <button type="button" disabled={busy} aria-pressed={mode === 'unclear'}
          onClick={() => { setMode('unclear'); setSaved(false); }}>{text.unclear}</button>
      </div>
      {mode === 'unclear' && !saved && (
        <form onSubmit={submit} className="analysis-feedback__form">
          <label htmlFor={`feedback-area-${message.id}`}>{text.area}</label>
          <select id={`feedback-area-${message.id}`} value={area}
            onChange={(event) => setArea(event.target.value)}>
            <option value="">{text.choose}</option>
            {Object.entries(AREA_LABELS[japanese ? 'ja' : 'en']).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <textarea value={detail} maxLength={1000} placeholder={text.placeholder}
            onChange={(event) => setDetail(event.target.value)} />
          <button type="submit" disabled={busy || (!area && !detail.trim())}>{text.submit}</button>
        </form>
      )}
      {saved && <p className="analysis-feedback__saved" role="status">{text.saved}</p>}
      {error && <p className="analysis-feedback__error" role="alert">{error}</p>}
    </section>
  );
}
