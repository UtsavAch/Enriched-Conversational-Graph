/**
 * D3 force simulation, driven from React without either library fighting the
 * other for the DOM.
 *
 * THE DIVISION OF LABOUR
 *
 * D3 owns the *maths*: the force simulation, the scales, the zoom transform.
 * React owns the *DOM*: every `<circle>`, `<line>` and `<text>` is a component.
 * There is no `d3.select().append()` anywhere in this codebase.
 *
 * The usual naive approach — letting D3 mutate the SVG directly — works until
 * React re-renders and blows away D3's changes, at which point you get bugs
 * that only appear when a filter toggles. Keeping the boundary at "D3 computes,
 * React renders" removes that class of bug entirely.
 *
 * THE PERFORMANCE PROBLEM, AND WHY IT IS SOLVED THIS WAY
 *
 * The simulation ticks ~60 times a second. Calling `setState` on every tick
 * with a fresh array would allocate and reconcile far more than necessary.
 *
 * Instead: the simulation mutates its node objects in place (which is what D3
 * does natively), positions are read from a ref, and a single
 * `requestAnimationFrame` loop bumps a counter to trigger at most one React
 * render per frame. Node components are memoised on their x/y, so a frame in
 * which a node has not moved costs nothing.
 *
 * This handles the scale this project needs (hundreds of nodes). If a
 * conversation ever produced thousands, the next step would be canvas
 * rendering rather than SVG — a change confined to the view components, because
 * this hook only produces positions.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationNodeDatum,
} from "d3-force";
import { scaleTime } from "d3-scale";
import type { EdgeView, GraphNodeDatum } from "@/types/api";

/**
 * A node once D3 has attached position and velocity to it.
 *
 * An intersection rather than `interface extends`, because `GraphNodeDatum` is
 * a discriminated union and an interface cannot extend one. The intersection
 * distributes over the union, so narrowing on `kind` still works downstream —
 * which is the whole reason the union exists.
 */
export type SimNode = GraphNodeDatum &
  SimulationNodeDatum & {
    /** Only present for interaction nodes; drives the timeline x position. */
    dateValue?: number;
  };

/** An edge after `forceLink` has replaced the id strings with node references. */
export interface SimEdge extends Omit<EdgeView, "source" | "target"> {
  source: SimNode;
  target: SimNode;
}

export interface Positioned {
  id: string;
  x: number;
  y: number;
}

/** `timestamp` is a full ISO 8601 datetime (or, for corpus-sourced turns, a
 *  bare `YYYY-MM-DD`); `Date` parses both natively, unlike a fixed d3 format. */
function parseTimestamp(iso: string | undefined): number | undefined {
  if (!iso) return undefined;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? undefined : t;
}

/** Node radius. Interaction nodes scale with how often the memory has
 *  re-surfaced them — retrieval + recurrence — which makes heavily-reused turns
 *  visually prominent. Capped so one hot node cannot dominate the layout.
 *
 *  Sized to comfortably fit the node's id label centred inside the shape —
 *  ids are short by design (`N_1`, `E_23`, `SN_8`, see `next_id()` in
 *  `core/schema/conversation.py`), so no truncation is needed at these sizes. */
export function nodeRadius(n: GraphNodeDatum): number {
  if (n.kind === "interaction") {
    const use = (n.data.recurrence_count ?? 0) + (n.data.retrieval_count ?? 0);
    return 15 + Math.min(10, use);
  }
  return n.kind === "entity" ? 15 : 13;
}

/** Link distance by edge group. Mentions pull tighter so entities cluster near
 *  the turns that mention them, rather than drifting to the rim. */
function linkDistance(e: SimEdge): number {
  if (e.group === "mention") return 55;
  if (e.group === "state_link") return 72;
  return 90;
}

interface Options {
  nodes: GraphNodeDatum[];
  edges: EdgeView[];
  width: number;
  height: number;
  mode: "graph" | "timeline";
}

export function useForceSimulation({
  nodes,
  edges,
  width,
  height,
  mode,
}: Options) {
  /**
   * D3 mutates the objects it is given, so the simulation's copies must be
   * distinct from the query cache's objects. Cloning here keeps the cached
   * server data immutable — otherwise React Query's data would silently sprout
   * x/y/vx/vy fields and equality checks elsewhere would misbehave.
   */
  const simNodes = useMemo<SimNode[]>(
    () =>
      nodes.map((n) =>
        n.kind === "interaction"
          ? { ...n, dateValue: parseTimestamp(n.data.timestamp) }
          : { ...n },
      ),
    [nodes],
  );

  const simEdges = useMemo(() => edges.map((e) => ({ ...e })), [edges]);

  const simRef = useRef<Simulation<SimNode, undefined> | null>(null);
  const nodesRef = useRef<SimNode[]>(simNodes);
  const [, forceRender] = useState(0);
  const frameRef = useRef<number | null>(null);

  // ── build / rebuild the simulation ──────────────────────────────────────
  useEffect(() => {
    if (!simNodes.length || !width || !height) return;

    nodesRef.current = simNodes;

    const sim = forceSimulation<SimNode>(simNodes)
      .force(
        "link",
        forceLink<SimNode, SimEdge>(simEdges as unknown as SimEdge[])
          .id((d) => d.id)
          .distance(linkDistance)
          .strength(0.55),
      )
      .force("charge", forceManyBody().strength(-280))
      .force(
        "collide",
        forceCollide<SimNode>().radius((d) => nodeRadius(d) + 14),
      );

    simRef.current = sim;

    /**
     * One render per animation frame, regardless of how many ticks occurred.
     * `forceRender` bumps a counter; the actual positions are read from the ref
     * by the component, so no array is allocated per frame.
     */
    let running = true;
    const loop = () => {
      if (!running) return;
      forceRender((n) => n + 1);
      frameRef.current = requestAnimationFrame(loop);
    };
    frameRef.current = requestAnimationFrame(loop);

    // Stop the render loop once the layout settles. A static graph should not
    // burn a frame budget forever.
    sim.on("end", () => {
      running = false;
    });

    return () => {
      running = false;
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      sim.stop();
      simRef.current = null;
    };
  }, [simNodes, simEdges, width, height]);

  // ── layout mode: force-directed vs. timeline ────────────────────────────
  const timeScale = useMemo(() => {
    const dated = simNodes.filter((n) => n.dateValue !== undefined);
    if (dated.length < 2) return null;
    const values = dated.map((n) => n.dateValue!);
    return scaleTime()
      .domain([Math.min(...values), Math.max(...values)])
      .range([90, Math.max(120, width - 90)]);
  }, [simNodes, width]);

  useEffect(() => {
    const sim = simRef.current;
    if (!sim || !width || !height) return;

    if (mode === "timeline" && timeScale) {
      /**
       * Timeline mode pins interactions to their date on the x axis and
       * separates the other kinds vertically: state nodes above the dialogue,
       * entities below. Both bands read at a glance and neither obscures the
       * turn sequence, which is what the timeline exists to show.
       */
      sim
        .force("center", null)
        .force(
          "x",
          forceX<SimNode>((d) =>
            d.kind === "interaction" && d.dateValue !== undefined
              ? timeScale(d.dateValue)
              : width / 2,
          ).strength((d) => (d.kind === "interaction" ? 0.9 : 0.04)),
        )
        .force(
          "y",
          forceY<SimNode>((d) =>
            d.kind === "interaction"
              ? height / 2
              : d.kind === "state"
                ? height / 2 - 140
                : height / 2 + 140,
          ).strength((d) => (d.kind === "interaction" ? 0.35 : 0.18)),
        );
    } else {
      sim
        .force("x", null)
        .force("y", null)
        .force("center", forceCenter(width / 2, height / 2));
    }

    sim.alpha(0.9).restart();

    // Restarting stops the simulation from being 'ended', so the render loop
    // needs waking too.
    let running = true;
    const loop = () => {
      if (!running) return;
      forceRender((n) => n + 1);
      frameRef.current = requestAnimationFrame(loop);
    };
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(loop);
    sim.on("end", () => {
      running = false;
    });

    return () => {
      running = false;
    };
  }, [mode, timeScale, width, height]);

  /**
   * Pin a node while it is dragged, and release it afterwards.
   *
   * Released rather than left pinned, deliberately: a pinned node distorts the
   * layout permanently, and the user's intent when dragging is almost always to
   * look at something, not to fix its position.
   */
  const dragNode = (
    id: string,
    x: number,
    y: number,
    phase: "start" | "move" | "end",
  ) => {
    const sim = simRef.current;
    const node = nodesRef.current.find((n) => n.id === id);
    if (!sim || !node) return;

    if (phase === "start") sim.alphaTarget(0.25).restart();
    if (phase === "end") {
      sim.alphaTarget(0);
      node.fx = null;
      node.fy = null;
      return;
    }
    node.fx = x;
    node.fy = y;
  };

  return {
    /** Live node objects. Mutated by D3 — read `.x` / `.y` during render. */
    simNodes: nodesRef.current,
    /** Edges with `source`/`target` resolved to node objects by `forceLink`. */
    simEdges: simEdges as unknown as SimEdge[],
    timeScale,
    dragNode,
  };
}
