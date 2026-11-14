import { BarVisualizer } from './elevenlabs/bar-visualizer';
import { stages } from '../demo';
import type { Turn } from '../demo';
import { useLanguage } from '../i18n';

export const replyDelay = 2200;
export const followupDelay = 1200;
export const responseDuration = (turn: Turn) =>
  turn.intent === 'payment' && !turn.replyText ? stages[3].at : replyDelay;

export function activityState(elapsed: number, duration: number) {
  if (elapsed < duration * 0.2) return 'connecting';
  if (elapsed < duration * 0.75) return 'thinking';
  return 'speaking';
}

export function ResponseActivity({
  elapsed,
  duration,
  reduced,
  followup = false,
}: {
  elapsed: number;
  duration: number;
  reduced: boolean;
  followup?: boolean;
}) {
  const { t } = useLanguage();
  const state = activityState(elapsed, duration);
  const labels = {
    connecting: 'Connecting…',
    thinking: 'Thinking…',
    speaking: 'Preparing your reply…',
  };
  return (
    <div className="response-activity" role="status" aria-live="polite">
      <BarVisualizer
        aria-hidden="true"
        className="thinking"
        state={reduced ? undefined : state}
        barCount={5}
        minHeight={30}
        maxHeight={95}
        centerAlign
        demo={!reduced && state === 'speaking'}
      />
      <span>
        {t(followup && state === 'speaking' ? 'Preparing a follow-up question…' : labels[state])}
      </span>
    </div>
  );
}
