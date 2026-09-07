import { useMemo } from 'react';
import { useUiStore } from '@/store/uiStore';
import type { GraphView } from '@/types/api';
import { EmptyState } from '@/components/States';
import { InteractionDetail } from './InteractionDetail';
import { EntityDetail } from './EntityDetail';
import { StateNodeDetail } from './StateNodeDetail';
import { RelationList } from './RelationList';
import './Inspector.css';

/**
 * Node detail.
 *
 * Reads from the already-fetched graph rather than calling
 * `/api/graph/{id}/node/{nodeId}`. The graph payload contains everything the
 * panel shows, so an extra request would add latency for nothing. The endpoint
 * still exists and is useful for scripting; it is simply not needed here.
 */
export function InspectorPanel({ graph }: { graph: GraphView | undefined }) {
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectNode = useUiStore((s) => s.selectNode);

  const selected = useMemo(() => {
    if (!graph || !selectedNodeId) return null;
    const interaction = graph.interaction_nodes.find((n) => n.id === selectedNodeId);
    if (interaction) return { kind: 'interaction' as const, data: interaction };
    const entity = graph.entities.find((n) => n.id === selectedNodeId);
    if (entity) return { kind: 'entity' as const, data: entity };
    const state = graph.state_nodes.find((n) => n.id === selectedNodeId);
    if (state) return { kind: 'state' as const, data: state };
    return null;
  }, [graph, selectedNodeId]);

  /** Every edge touching the selection, in either direction, with the
   *  neighbour's display name resolved for the list. */
  const relations = useMemo(() => {
    if (!graph || !selectedNodeId) return [];
    const nameOf = (id: string): string => {
      const i = graph.interaction_nodes.find((n) => n.id === id);
      if (i) return i.summary || i.reference || i.question;
      const e = graph.entities.find((n) => n.id === id);
      if (e) return e.name;
      const s = graph.state_nodes.find((n) => n.id === id);
      return s ? s.label : id;
    };
    return graph.edges
      .filter((e) => e.source === selectedNodeId || e.target === selectedNodeId)
      .map((e) => {
        const isOut = e.source === selectedNodeId;
        const other = isOut ? e.target : e.source;
        return {
          direction: (isOut ? 'out' : 'in') as 'in' | 'out',
          other,
          other_name: nameOf(other),
          label: e.label,
          group: e.group,
          strength: 1,
        };
      });
  }, [graph, selectedNodeId]);

  if (!selected) {
    return (
      <div className="inspector">
        <EmptyState
          title="Nothing selected"
          hint="Click a node in the graph, or a turn in the transcript, to inspect its fields and every edge attached to it."
        />
      </div>
    );
  }

  return (
    <div className="inspector">
      {selected.kind === 'interaction' && <InteractionDetail node={selected.data} graph={graph!} />}
      {selected.kind === 'entity' && <EntityDetail node={selected.data} />}
      {selected.kind === 'state' && <StateNodeDetail node={selected.data} />}

      <div className="inspector-divider" />
      <RelationList relations={relations} onJump={selectNode} />
    </div>
  );
}
