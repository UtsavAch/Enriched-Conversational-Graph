import { useMemo, useState } from "react";
import { useUiStore } from "@/store/uiStore";
import type { EntityView, GraphView } from "@/types/api";
import { Badge } from "@/components/Badge";
import { EmptyState } from "@/components/States";
import { formatDate } from "@/lib/format";
import "./Entities.css";

/** `E_12` -> 12, so ordering matches creation order even past `E_9`. */
function idOrdinal(id: string): number {
  const m = id.match(/(\d+)\s*$/);
  return m ? Number(m[1]) : Number.POSITIVE_INFINITY;
}

/**
 * Every entity in the conversation, oldest first.
 *
 * A flat list next to the Inspector rather than folded into it: the graph
 * canvas only shows an entity once it has been drawn into view, so this is
 * the one place to confirm what extraction actually found, in bulk, without
 * hunting for each node on the canvas.
 */
export function EntitiesPanel({ graph }: { graph: GraphView | undefined }) {
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectNode = useUiStore((s) => s.selectNode);
  const [query, setQuery] = useState("");

  const entities = useMemo(() => {
    if (!graph) return [];
    const sorted = [...graph.entities].sort(
      (a, b) => idOrdinal(a.id) - idOrdinal(b.id) || a.id.localeCompare(b.id),
    );
    const q = query.trim().toLowerCase();
    if (!q) return sorted;
    return sorted.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.id.toLowerCase().includes(q) ||
        e.type.toLowerCase().includes(q),
    );
  }, [graph, query]);

  if (!graph) {
    return (
      <div className="entities">
        <EmptyState title="No conversation selected" />
      </div>
    );
  }

  return (
    <div className="entities">
      <p className="inspector-kind">memory graph</p>
      <h2 className="inspector-title">Entities</h2>
      <p className="inspector-lede">
        Every entity extracted from the conversation, oldest first.
      </p>

      <input
        className="list-search"
        value={query}
        placeholder="Filter by name, id or type…"
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="inspector-divider" />

      {entities.length === 0 ? (
        <EmptyState title={query ? "No matches" : "No entities yet"} />
      ) : (
        <ul className="entity-list">
          {entities.map((entity) => (
            <EntityRow
              key={entity.id}
              entity={entity}
              selected={entity.id === selectedNodeId}
              onSelect={() => selectNode(entity.id)}
              onJumpToTurn={(id) => selectNode(id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function EntityRow({
  entity,
  selected,
  onSelect,
  onJumpToTurn,
}: {
  entity: EntityView;
  selected: boolean;
  onSelect: () => void;
  onJumpToTurn: (id: string) => void;
}) {
  return (
    <li className={`entity-item${selected ? " active" : ""}`}>
      <button className="entity-main" onClick={onSelect}>
        <div className="entity-head">
          <span className="entity-name">{entity.name}</span>
          <Badge bg="var(--c-entity-soft)" fg="var(--c-entity)">
            {entity.type}
          </Badge>
        </div>
        <div className="entity-meta">
          <span className="entity-id">{entity.id}</span>
          {" · "}
          {formatDate(entity.timestamp)}
        </div>
      </button>

      <div className="entity-mentions">
        <span className="field-note">
          mentioned in {entity.mentioned_in.length} turn
          {entity.mentioned_in.length === 1 ? "" : "s"}
        </span>
        <div className="tag-row" style={{ marginTop: 4 }}>
          {entity.mentioned_in.map((turnId) => (
            <button
              key={turnId}
              className="turn-chip"
              title={`Jump to ${turnId}`}
              onClick={() => onJumpToTurn(turnId)}
            >
              {turnId}
            </button>
          ))}
        </div>
      </div>
    </li>
  );
}
