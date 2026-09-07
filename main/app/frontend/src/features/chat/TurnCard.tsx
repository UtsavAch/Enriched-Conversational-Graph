import { forwardRef } from 'react';
import { Badge } from '@/components/Badge';
import { STATUS_STYLE } from '@/lib/graphStyles';
import { humanize } from '@/lib/format';
import type { InteractionNodeView } from '@/types/api';

interface Props {
  turn: InteractionNodeView;
  active: boolean;
  onSelect: () => void;
}

const TurnCardBase = forwardRef<HTMLDivElement, Props>(({ turn, active, onSelect }, ref) => {
  const status = STATUS_STYLE[turn.epistemic_status];

  return (
    <div
      ref={ref}
      className={`turn ${active ? 'turn-active' : ''}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(); } }}
    >
      <div className="turn-meta">
        <span className="turn-id">{turn.id}</span>
        <div className="turn-meta-right">
          {/* A superseded turn is flagged in the transcript, not only in the
              inspector — otherwise a reader scrolling the history has no way to
              know a decision was later reversed. */}
          {turn.epistemic_status !== 'resolved' && (
            <Badge bg={status.bg} fg={status.fg}>{turn.epistemic_status}</Badge>
          )}
          <span className="turn-date">{turn.date}</span>
        </div>
      </div>

      <div className="bubble bubble-q">
        <span className="bubble-tag">you</span>
        {turn.question}
      </div>
      <div className="bubble bubble-a">
        <span className="bubble-tag">assistant</span>
        {turn.answer}
      </div>

      {(turn.grounded_by.length > 0 || turn.speech_act !== 'information') && (
        <div className="turn-footer">
          <span className="turn-act">{humanize(turn.speech_act)}</span>
          {turn.grounded_by.length > 0 && (
            <span className="turn-grounded" title={turn.grounded_by.join(', ')}>
              grounded · {turn.grounded_by.length}
            </span>
          )}
        </div>
      )}
    </div>
  );
});
TurnCardBase.displayName = 'TurnCard';

/** Optimistic placeholder shown while the pipeline runs. */
function Pending({ question }: { question: string }) {
  return (
    <div className="turn turn-pending">
      <div className="turn-meta"><span className="turn-id">…</span></div>
      <div className="bubble bubble-q"><span className="bubble-tag">you</span>{question}</div>
      <div className="bubble bubble-a bubble-thinking">
        <span className="bubble-tag">assistant</span>
        <span className="dots"><i /><i /><i /></span>
      </div>
    </div>
  );
}

export const TurnCard = Object.assign(TurnCardBase, { Pending });
