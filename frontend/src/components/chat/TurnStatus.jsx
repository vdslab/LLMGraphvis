import { Loader2, Check, Brain, Wrench } from 'lucide-react';
import Disclosure from './Disclosure';

/**
 * What the agent is doing right now.
 *
 * Three different things used to be shown here under one "Thinking Process"
 * heading: backend pipeline steps, the tool currently executing, and the
 * model's reasoning. They are separated now — the reasoning is the only one
 * the word "thinking" describes, and it is the only one that stays folded,
 * because it is the one the user is least often reading.
 */
const TurnStatus = ({ isLoading, progressSteps, runningTool, thinkingMessage }) => {
  const hasProgress = progressSteps && progressSteps.length > 0;
  if (!isLoading && !hasProgress && !runningTool && !thinkingMessage) return null;

  const current = runningTool
    ? { icon: <Wrench size={13} aria-hidden />, label: runningTool.name, kind: 'tool' }
    : hasProgress
      ? { icon: null, label: progressSteps[progressSteps.length - 1].label }
      : { icon: null, label: 'Working' };

  const done = hasProgress ? progressSteps.slice(0, -1) : [];

  return (
    <div className="turnstatus" role="status" aria-live="polite">
      {done.map((step, idx) => (
        <div key={idx} className="turnstatus__step turnstatus__step--done">
          <Check size={13} aria-hidden />
          <span>{step.label}</span>
        </div>
      ))}

      <div className="turnstatus__step turnstatus__step--active">
        <Loader2 size={13} className="spin" aria-hidden />
        {current.icon}
        <span className={current.kind === 'tool' ? 'turnstatus__tool' : undefined}>
          {current.label}
        </span>
      </div>

      {thinkingMessage && (
        <Disclosure
          icon={<Brain size={13} aria-hidden />}
          label="Thinking"
          tone="thought"
        >
          <pre className="thought__text">{thinkingMessage}</pre>
        </Disclosure>
      )}
    </div>
  );
};

export default TurnStatus;
