import { memo } from "react";
import { GROUP_DASH, edgeColor } from "@/lib/graphStyles";
import type { SimEdge } from "./useForceSimulation";

interface Props {
  edge: SimEdge;
  /** Endpoint coordinates, extracted by the parent on every render.
   *  `edge.source`/`edge.target` are mutated in place by the simulation, so a
   *  memo comparator can't detect movement by reading through `edge` itself —
   *  it would always be comparing the same object to itself. Primitives here
   *  are genuinely fresh each tick, the same trick GraphNode uses for x/y. */
  x1: number;
  y1: number;
  x2: number;
  y2: number;
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
function GraphEdgeImpl({
  edge,
  x1,
  y1,
  x2,
  y2,
  dimmed,
  highlighted,
  markerId,
}: Props) {
  const color = edgeColor(edge.group, edge.label);
  const base = edge.group === "pragmatic" ? 1.8 : 1.2;

  return (
    <line
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      stroke={color}
      strokeWidth={highlighted ? base + 1.2 : base}
      strokeDasharray={GROUP_DASH[edge.group]}
      markerEnd={`url(#${markerId})`}
      opacity={dimmed ? 0.05 : highlighted ? 1 : 0.85}
    />
  );
}

export const GraphEdge = memo(
  GraphEdgeImpl,
  (a, b) =>
    a.x1 === b.x1 &&
    a.y1 === b.y1 &&
    a.x2 === b.x2 &&
    a.y2 === b.y2 &&
    a.dimmed === b.dimmed &&
    a.highlighted === b.highlighted,
);
