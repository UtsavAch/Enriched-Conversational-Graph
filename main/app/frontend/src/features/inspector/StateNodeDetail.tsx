import { Badge } from '@/components/Badge';
import { STATUS_STYLE } from '@/lib/graphStyles';
import { humanize } from '@/lib/format';
import type { StateNodeView } from '@/types/api';
import { Field } from './InteractionDetail';

const TYPE_DESCRIPTION: Record<string, string> = {
  goal: 'an objective the conversation is working towards',
  decision: 'a choice that was made and now stands',
  constraint: 'a requirement that must keep holding',
  open_question: 'something raised and explicitly not settled',
};

export function StateNodeDetail({ node }: { node: StateNodeView }) {
  const status = STATUS_STYLE[node.status];
  return (
    <>
      <p className="inspector-kind">state node · {humanize(node.type)}</p>
      <h2 className="inspector-title">{node.label}</h2>

      <div className="badge-row">
        <Badge bg={status.bg} fg={status.fg}>{node.status}</Badge>
        <Badge>{node.id}</Badge>
      </div>

      <p className="inspector-lede">{TYPE_DESCRIPTION[node.type]}</p>

      <Field label="Created at">{node.creation_turn}</Field>
      <Field label="Last updated">
        {node.last_updated_turn}
        {node.last_updated_turn === node.creation_turn && (
          <span className="field-note">unchanged since creation</span>
        )}
      </Field>
    </>
  );
}
