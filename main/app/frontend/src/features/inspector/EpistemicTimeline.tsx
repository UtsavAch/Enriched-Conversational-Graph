import { STATUS_STYLE } from '@/lib/graphStyles';
import type { EpistemicEvent } from '@/types/api';

/**
 * The audit trail of a node's epistemic status.
 *
 * This is the clearest visible payoff of the enriched schema. A plain
 * "superseded" badge tells you a claim no longer stands; this tells you *which
 * turn* superseded it and *by what relation* — the difference between knowing
 * the memory self-corrected and being able to show how.
 *
 * Rendered only when there is more than one event, since a lone `creation`
 * entry says nothing a reader cannot already see.
 */
export function EpistemicTimeline({ history }: { history: EpistemicEvent[] }) {
  return (
    <ol className="epistemic-timeline">
      {history.map(([causedBy, trigger, status], i) => {
        const style = STATUS_STYLE[status];
        return (
          <li key={`${causedBy}-${i}`} className="epistemic-event">
            <span className="epistemic-marker" style={{ background: style.fg }} aria-hidden />
            <div className="epistemic-body">
              <span className="epistemic-status" style={{ color: style.fg }}>{status}</span>
              <span className="epistemic-cause">
                {trigger === 'creation' ? 'on creation' : `via ${trigger} from ${causedBy}`}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
