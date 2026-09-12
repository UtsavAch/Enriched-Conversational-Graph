import { useMemo, useRef } from "react";
import { useUiStore } from "@/store/uiStore";
import { edgeColor } from "@/lib/graphStyles";
import type { EdgeGroup, GraphNodeDatum, GraphView } from "@/types/api";
import { GraphEdge } from "./GraphEdge";
import { GraphNode } from "./GraphNode";
import { TimelineAxis } from "./TimelineAxis";
import { useElementSize } from "./useElementSize";
import { useForceSimulation } from "./useForceSimulation";
import { useZoomPan } from "./useZoomPan";
import "./GraphCanvas.css";

/**
 * The graph view.
 *
 * Responsibilities are kept narrow on purpose: this component composes the
 * simulation, the zoom behaviour and the node/edge components, and computes
 * what is dimmed. It does not fetch, does not own selection, and does not
 * know how a node is styled.
 */
export function GraphCanvas({ graph }: { graph: GraphView }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const { width, height } = useElementSize(wrapRef);

  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectNode = useUiStore((s) => s.selectNode);
  const viewMode = useUiStore((s) => s.viewMode);
  const nodeFilters = useUiStore((s) => s.nodeFilters);
  const edgeFilters = useUiStore((s) => s.edgeFilters);

  const { transform, reset } = useZoomPan(svgRef);

  // Flatten the three node layers into the discriminated union the graph draws.
  const nodes = useMemo<GraphNodeDatum[]>(
    () => [
      ...graph.interaction_nodes.map((d) => ({
        id: d.id,
        kind: "interaction" as const,
        data: d,
      })),
      ...graph.entities.map((d) => ({
        id: d.id,
        kind: "entity" as const,
        data: d,
      })),
      ...graph.state_nodes.map((d) => ({
        id: d.id,
        kind: "state" as const,
        data: d,
      })),
    ],
    [graph],
  );

  const { simNodes, simEdges, timeScale, dragNode } = useForceSimulation({
    nodes,
    edges: graph.edges,
    width,
    height,
    mode: viewMode,
  });

  /**
   * Neighbours of the selection. Everything else dims rather than disappears —
   * keeping the surrounding structure faintly visible preserves the sense of
   * where the selected node sits, which hiding would destroy.
   */
  const connected = useMemo(() => {
    if (!selectedNodeId) return null;
    const set = new Set<string>([selectedNodeId]);
    for (const e of graph.edges) {
      if (e.source === selectedNodeId) set.add(e.target);
      if (e.target === selectedNodeId) set.add(e.source);
    }
    return set;
  }, [selectedNodeId, graph.edges]);

  // One arrow marker per colour in use. SVG markers cannot inherit stroke, so
  // a marker per colour is the only way to get matching arrowheads.
  const markers = useMemo(() => {
    const map = new Map<string, string>();
    graph.edges.forEach((e) => {
      const c = edgeColor(e.group, e.label);
      if (!map.has(c)) map.set(c, `arrow-${map.size}`);
    });
    return map;
  }, [graph.edges]);

  const visibleNodeIds = useMemo(() => {
    const set = new Set<string>();
    simNodes.forEach((n) => {
      if (nodeFilters[n.kind]) set.add(n.id);
    });
    return set;
  }, [simNodes, nodeFilters]);

  const labelScale = 1 / Math.max(transform.k, 0.5);

  return (
    <div className="graph-canvas" ref={wrapRef}>
      <svg
        ref={svgRef}
        className="graph-svg"
        onClick={() => selectNode(null)}
        role="application"
        aria-label="Conversation memory graph"
      >
        <defs>
          {[...markers.entries()].map(([color, id]) => (
            <marker
              key={id}
              id={id}
              viewBox="0 -4 8 8"
              refX={8}
              refY={0}
              markerWidth={6}
              markerHeight={6}
              orient="auto"
            >
              <path d="M0,-4L8,0L0,4" fill={color} />
            </marker>
          ))}
        </defs>

        {viewMode === "timeline" && timeScale && (
          <TimelineAxis scale={timeScale} height={height} />
        )}

        <g transform={transform.toString()}>
          <g className="edge-layer">
            {simEdges.map((e, i) => {
              const sourceId = e.source?.id ?? "";
              const targetId = e.target?.id ?? "";
              if (!edgeFilters[e.group as EdgeGroup]) return null;
              if (
                !visibleNodeIds.has(sourceId) ||
                !visibleNodeIds.has(targetId)
              )
                return null;
              const touches =
                selectedNodeId === sourceId || selectedNodeId === targetId;
              return (
                <GraphEdge
                  key={`${sourceId}-${targetId}-${e.label}-${i}`}
                  edge={e}
                  x1={e.source?.x ?? 0}
                  y1={e.source?.y ?? 0}
                  x2={e.target?.x ?? 0}
                  y2={e.target?.y ?? 0}
                  dimmed={Boolean(selectedNodeId) && !touches}
                  highlighted={touches}
                  markerId={markers.get(edgeColor(e.group, e.label)) ?? ""}
                />
              );
            })}
          </g>

          <g className="node-layer">
            {simNodes.map((n) => {
              if (!nodeFilters[n.kind]) return null;
              return (
                <GraphNode
                  key={n.id}
                  node={n}
                  x={n.x ?? 0}
                  y={n.y ?? 0}
                  dimmed={Boolean(connected) && !connected!.has(n.id)}
                  selected={selectedNodeId === n.id}
                  onSelect={selectNode}
                  onDrag={dragNode}
                  labelScale={labelScale}
                />
              );
            })}
          </g>
        </g>
      </svg>

      <div className="graph-hint">
        drag nodes · scroll to zoom · click to inspect
      </div>

      {transform.k !== 1 && (
        <button className="graph-reset" onClick={reset}>
          Reset view
        </button>
      )}
    </div>
  );
}
