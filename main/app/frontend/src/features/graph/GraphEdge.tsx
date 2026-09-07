import { memo } from 'react';
import { GROUP_DASH, edgeColor } from '@/lib/graphStyles';
import type { SimEdge } from './useForceSimulation';

interface Props {
  edge: SimEdge;
  dimmed: boolean;
  highlighted: boolean;
  markerId: string;
}

/**
 * One edge.
 *
 * Pragmatic edges are drawn solid and slightly heavier than the rest. That is
 * not decoration: they are the discourse relations this work adds, so they
 * should be the thing the eye lands on. Mentions and citations recede because
 * they are derived rather than classified.
 */
function GraphEdgeImpl({ edge, dimmed, highlighted, markerId }: Props) {
  const color = edgeColor(edge.group, edge.label);
  const base = edge.group === 'pragmatic' ? 1.8 : 1.2;

  return (
    <line
      x1={edge.source.x} y1={edge.source.y}
      x2={edge.target.x} y2={edge.target.y}
      stroke={color}
      strokeWidth={highlighted ? base + 1.2 : base}
      strokeDasharray={GROUP_DASH[edge.group]}
      markerEnd={`url(#${markerId})`}
      opacity={dimmed ? 0.05 : highlighted ? 1 : 0.85}
    />
  );
}

export const GraphEdge = memo(GraphEdgeImpl, (a, b) =>
  a.edge.source.x === b.edge.source.x && a.edge.source.y === b.edge.source.y &&
  a.edge.target.x === b.edge.target.x && a.edge.target.y === b.edge.target.y &&
  a.dimmed === b.dimmed && a.highlighted === b.highlighted,
);
