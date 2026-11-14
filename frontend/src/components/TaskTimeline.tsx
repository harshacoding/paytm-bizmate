import type { Task } from '../api/types';

export function TaskTimeline({ task }: { task: Task }) {
  return (
    <section className="card timeline" aria-label="Task details">
      <div className="section-title">
        <div>
          <span className="eyebrow">CURRENT TASK</span>
          <h2>{task.goal}</h2>
        </div>
        <span className="badge">{task.status.replaceAll('_', ' ')}</span>
      </div>
      <p className="next-action">{task.next_action}</p>
      <ol>
        {task.events.map((event) => (
          <li key={event.event_id}>
            <span className="event-dot" />
            <div>
              <p>{event.message}</p>
              <time dateTime={event.occurred_at}>
                {new Date(event.occurred_at).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </time>
            </div>
          </li>
        ))}
      </ol>
      <div className="empty-evidence">No execution receipt or verification yet.</div>
    </section>
  );
}
