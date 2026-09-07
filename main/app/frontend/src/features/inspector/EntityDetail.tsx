import { Badge } from '@/components/Badge';
import type { EntityView } from '@/types/api';
import { Field } from './InteractionDetail';

export function EntityDetail({ node }: { node: EntityView }) {
  return (
    <>
      <p className="inspector-kind">entity</p>
      <h2 className="inspector-title">{node.name}</h2>

      <div className="badge-row">
        <Badge bg="var(--c-entity-soft)" fg="var(--c-entity)">{node.type}</Badge>
        <Badge>{node.id}</Badge>
      </div>

      <Field label={`Mentioned in ${node.mentioned_in.length} turn${node.mentioned_in.length === 1 ? '' : 's'}`}>
        <div className="tag-row">
          {node.mentioned_in.map((id) => <Badge key={id}>{id}</Badge>)}
        </div>
        {/* Worth surfacing: entity matching is exact on normalised surface form,
            so near-duplicates stay separate. That under-merging is a known
            limitation and shows up in the Phase 3 entity P/R numbers. */}
        <span className="field-note">
          entities match on exact normalised name; near-duplicates are not merged
        </span>
      </Field>
    </>
  );
}
