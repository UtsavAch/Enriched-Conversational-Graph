import { memo, useEffect, useRef } from 'react';
import { drag } from 'd3-drag';
import { select } from 'd3-selection';
import { NODE_COLOR, NODE_FILL, isInactiveState, stateNodeColor, stateNodeFill } from '@/lib/graphStyles';
import { nodeRadius, type SimNode } from './useForceSimulation';

interface Props {
  node: SimNode;
  x: number;
  y: number;
  dimmed: boolean;
  selected: boolean;
  onSelect: (id: string) => void;
  onDrag: (id: string, x: number, y: number, phase: 'start' | 'move' | 'end') => void;
  /** Inverse of the zoom scale — keeps labels legible at any zoom level. */
  labelScale: number;
}

/**
 * One node.
 *
 * Shape encodes kind, so the graph stays readable in greyscale and for
 * colour-blind readers: circle = interaction, diamond = entity,
 * rounded rectangle = state node.
 *
 * Memoised on position and visual state. During a simulation frame most nodes
 * have not moved, so most of these re-renders cost nothing.
 */
function GraphNodeImpl({ node, x, y, dimmed, selected, onSelect, onDrag, labelScale }: Props) {
  const gRef = useRef<SVGGElement>(null);

  // d3-drag handles pointer capture and touch, which is fiddly to redo by hand.
  // It is attached to the element but never mutates it — the handler only calls
  // back into the simulation.
  useEffect(() => {
    const el = gRef.current;
    if (!el) return;
    const behavior = drag<SVGGElement, unknown>()
      .on('start', (event) => { event.sourceEvent.stopPropagation(); onDrag(node.id, event.x, event.y, 'start'); })
      .on('drag', (event) => onDrag(node.id, event.x, event.y, 'move'))
      .on('end', () => onDrag(node.id, 0, 0, 'end'));
    select(el).call(behavior);
    return () => { select(el).on('.drag', null); };
  }, [node.id, onDrag]);

  const r = nodeRadius(node);
  const opacity = dimmed ? 0.12 : 1;

  let stroke: string;
  let fill: string;
  let inactive = false;

  if (node.kind === 'interaction') {
    stroke = NODE_COLOR.interaction; fill = NODE_FILL.interaction;
  } else if (node.kind === 'entity') {
    stroke = NODE_COLOR.entity; fill = NODE_FILL.entity;
  } else {
    stroke = stateNodeColor(node.data.type);
    fill = stateNodeFill(node.data.type);
    inactive = isInactiveState(node.data.status);
  }

  const label = node.kind === 'interaction' ? node.data.summary || node.data.question
    : node.kind === 'entity' ? node.data.name : node.data.label;

  return (
    <g
      ref={gRef}
      transform={`translate(${x},${y})`}
      opacity={opacity}
      style={{ cursor: 'pointer' }}
      onClick={(e) => { e.stopPropagation(); onSelect(node.id); }}
      tabIndex={0}
      role="button"
      aria-label={`${node.kind} ${node.id}: ${label}`}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(node.id); } }}
    >
      <title>{`${node.id} — ${label}`}</title>

      {node.kind === 'interaction' && (
        <circle r={r} fill={fill} stroke={stroke} strokeWidth={selected ? 3 : 2} />
      )}
      {node.kind === 'entity' && (
        <rect
          width={r * 1.5} height={r * 1.5} x={-r * 0.75} y={-r * 0.75}
          transform="rotate(45)" fill={fill} stroke={stroke} strokeWidth={selected ? 3 : 2}
        />
      )}
      {node.kind === 'state' && (
        <rect
          width={r * 2.2} height={r * 1.5} x={-r * 1.1} y={-r * 0.75} rx={5}
          fill={fill} stroke={stroke} strokeWidth={selected ? 3 : 2}
          opacity={inactive ? 0.55 : 1}
          // A dashed outline marks a state node that is no longer in force,
          // so status is legible without reading the label.
          strokeDasharray={inactive ? '3,2' : undefined}
        />
      )}

      {/* Selection ring sits outside the shape so it never obscures the fill. */}
      {selected && (
        <circle r={r + 7} fill="none" stroke={stroke} strokeWidth={1} opacity={0.45} />
      )}

      <text
        className="node-label"
        textAnchor="middle"
        y={r + 12}
        transform={`scale(${labelScale})`}
        transform-origin={`0 ${r + 12}`}
      >
        {node.id}
      </text>
    </g>
  );
}

export const GraphNode = memo(GraphNodeImpl, (a, b) =>
  a.x === b.x && a.y === b.y &&
  a.dimmed === b.dimmed && a.selected === b.selected &&
  a.labelScale === b.labelScale && a.node === b.node,
);
