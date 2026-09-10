import { Badge } from "@/components/Badge";
import { STATUS_STYLE } from "@/lib/graphStyles";
import { formatDateTime, humanize } from "@/lib/format";
import type { GraphView, InteractionNodeView } from "@/types/api";
import { EpistemicTimeline } from "./EpistemicTimeline";

export function InteractionDetail({
  node,
  graph,
}: {
  node: InteractionNodeView;
  graph: GraphView;
}) {
  const status = STATUS_STYLE[node.epistemic_status];
  const entityNames = node.named_entities.map(
    (id) => graph.entities.find((e) => e.id === id)?.name ?? id,
  );

  return (
    <>
      <p className="inspector-kind">interaction node</p>
      <h2 className="inspector-title">{node.id}</h2>

      <div className="badge-row">
        <Badge bg="var(--c-interaction-soft)" fg="var(--c-interaction)">
          {humanize(node.speech_act)}
        </Badge>
        <Badge bg={status.bg} fg={status.fg}>
          {node.epistemic_status}
        </Badge>
        {node.timestamp && (
          <Badge title={node.timestamp}>{formatDateTime(node.timestamp)}</Badge>
        )}
      </div>

      <div className="qa-block">
        <p className="qa-role">question</p>
        <p className="qa-text">{node.question}</p>
      </div>
      <div className="qa-block">
        <p className="qa-role">answer</p>
        <p className="qa-text">{node.answer}</p>
      </div>

      {node.summary && (
        <Field label="Summary">
          {node.summary}
          {/* Naming the compression tier matters: this is the string that gets
              injected when a graph entry wins a context slot, so seeing it is
              seeing what the agent will actually read. */}
          <span className="field-note">
            injected when this turn is reached via graph expansion
          </span>
        </Field>
      )}
      {node.reference && <Field label="Reference">{node.reference}</Field>}

      {entityNames.length > 0 && (
        <Field label="Entities mentioned">
          <div className="tag-row">
            {entityNames.map((name) => (
              <Badge
                key={name}
                bg="var(--c-entity-soft)"
                fg="var(--c-entity)"
                mono={false}
              >
                {name}
              </Badge>
            ))}
          </div>
        </Field>
      )}

      {node.grounded_by.length > 0 && (
        <Field label="Grounded by">
          <div className="tag-row">
            {node.grounded_by.map((id) => (
              <Badge key={id} bg="var(--neutral-soft)" fg="var(--ink-soft)">
                {id}
              </Badge>
            ))}
          </div>
          {/* Stating the separation in the UI keeps ADR-002 visible: document
              chunks are provenance, not part of the discourse graph. */}
          <span className="field-note">
            external document chunks — provenance only, not graph edges
          </span>
        </Field>
      )}

      <Field label="Retrieval / recurrence">
        {node.retrieval_count} / {node.recurrence_count}
        <span className="field-note">
          how often this turn has been re-surfaced by the memory
        </span>
      </Field>

      {node.epistemic_history.length > 1 && (
        <Field label="Epistemic history">
          <EpistemicTimeline history={node.epistemic_history} />
        </Field>
      )}
    </>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="field">
      <p className="field-label">{label}</p>
      <div className="field-value">{children}</div>
    </div>
  );
}
