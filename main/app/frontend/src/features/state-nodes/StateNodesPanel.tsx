import { useMemo, useState } from "react";
import { useUiStore } from "@/store/uiStore";
import type { EdgeView, GraphView, StateNodeView } from "@/types/api";
import { Badge } from "@/components/Badge";
import { EmptyState } from "@/components/States";
import { STATUS_STYLE, stateNodeColor, stateNodeFill } from "@/lib/graphStyles";
import { formatDate, humanize } from "@/lib/format";
import "./StateNodes.css";

/** `SN_12` -> 12, so ordering matches creation order even past `SN_9`. */
function idOrdinal(id: string): number {
  const m = id.match(/(\d+)\s*$/);
  return m ? Number(m[1]) : Number.POSITIVE_INFINITY;
}

/**
 * Every state node in the conversation, oldest first.
 *
 * Goals, decisions, constraints and open questions are the thing this app
 * argues is worth tracking as its own graph layer — so unlike entities, they
 * deserve a list that shows the full lifecycle at a glance: type, status,
 * and every turn that created, updated or related to it (W4's `relates`),
 * rather than making you click through the canvas to find them.
 */
export function StateNodesPanel({ graph }: { graph: GraphView | undefined }) {
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectNode = useUiStore((s) => s.selectNode);
  const [query, setQuery] = useState("");

  const stateNodes = useMemo(() => {
    if (!graph) return [];
    const sorted = [...graph.state_nodes].sort(
      (a, b) => idOrdinal(a.id) - idOrdinal(b.id) || a.id.localeCompare(b.id),
    );
    const q = query.trim().toLowerCase();
    if (!q) return sorted;
    return sorted.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q) ||
        s.type.toLowerCase().includes(q) ||
        s.status.toLowerCase().includes(q),
    );
  }, [graph, query]);

  /** Every `state_link` edge (creates / updates / relates), grouped by the
   *  state node it points at — the full audit trail, not just first-and-last. */
  const linksByNode = useMemo(() => {
    const map = new Map<string, EdgeView[]>();
    if (!graph) return map;
    for (const edge of graph.edges) {
      if (edge.group !== "state_link") continue;
      const list = map.get(edge.target);
      if (list) list.push(edge);
      else map.set(edge.target, [edge]);
    }
    for (const list of map.values()) {
      list.sort((a, b) => idOrdinal(a.source) - idOrdinal(b.source));
    }
    return map;
  }, [graph]);

  if (!graph) {
    return (
      <div className="state-nodes">
        <EmptyState title="No conversation selected" />
      </div>
    );
  }

  return (
    <div className="state-nodes">
      <p className="inspector-kind">memory graph</p>
      <h2 className="inspector-title">State nodes</h2>
      <p className="inspector-lede">
        Goals, decisions, constraints and open questions tracked across the
        conversation, oldest first.
      </p>

      <input
        className="list-search"
        value={query}
        placeholder="Filter by label, id, type or status…"
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="inspector-divider" />

      {stateNodes.length === 0 ? (
        <EmptyState title={query ? "No matches" : "No state nodes yet"} />
      ) : (
        <ul className="state-node-list">
          {stateNodes.map((node) => (
            <StateNodeRow
              key={node.id}
              node={node}
              links={linksByNode.get(node.id) ?? []}
              selected={node.id === selectedNodeId}
              onSelect={() => selectNode(node.id)}
              onJumpToTurn={(id) => selectNode(id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function StateNodeRow({
  node,
  links,
  selected,
  onSelect,
  onJumpToTurn,
}: {
  node: StateNodeView;
  links: EdgeView[];
  selected: boolean;
  onSelect: () => void;
  onJumpToTurn: (id: string) => void;
}) {
  const status = STATUS_STYLE[node.status];

  return (
    <li className={`state-node-item${selected ? " active" : ""}`}>
      <button className="state-node-main" onClick={onSelect}>
        <span className="state-node-label">{node.label}</span>
        <div className="badge-row" style={{ marginBottom: 0 }}>
          <Badge bg={stateNodeFill(node.type)} fg={stateNodeColor(node.type)}>
            {humanize(node.type)}
          </Badge>
          <Badge bg={status.bg} fg={status.fg}>
            {node.status}
          </Badge>
          <Badge>{node.id}</Badge>
        </div>
        <div className="state-node-meta">{formatDate(node.timestamp)}</div>
      </button>

      <div className="state-node-turns">
        <span className="field-note">
          touched by {links.length} turn{links.length === 1 ? "" : "s"}
        </span>
        <div className="tag-row" style={{ marginTop: 4 }}>
          {links.map((edge, i) => (
            <button
              key={`${edge.source}-${edge.label}-${i}`}
              className="turn-chip"
              title={`Jump to ${edge.source}`}
              onClick={() => onJumpToTurn(edge.source)}
            >
              {edge.label} · {edge.source}
            </button>
          ))}
        </div>
      </div>
    </li>
  );
}
