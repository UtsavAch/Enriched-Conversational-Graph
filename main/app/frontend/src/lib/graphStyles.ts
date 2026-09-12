/**
 * The mapping from schema values to visual encoding.
 *
 * Kept as data in one module rather than as conditionals inside components,
 * because the encoding is a design decision that should be reviewable on its
 * own. Adding a sixth pragmatic relation should be an edit here, not a hunt
 * through JSX.
 *
 * Colours reference CSS custom properties so the palette lives in one place
 * (`styles/tokens.css`) and a theme change does not touch TypeScript.
 */
import type {
  EdgeGroup,
  EpistemicStatus,
  StateNodeStatus,
  StateNodeType,
} from "@/types/api";

export const NODE_COLOR = {
  interaction: "var(--c-interaction)",
  entity: "var(--c-entity)",
  goal: "var(--c-goal)",
  constraint: "var(--c-constraint)",
  decision: "var(--c-decision)",
  open_question: "var(--c-question)",
} as const;

export const NODE_FILL = {
  interaction: "var(--c-interaction-soft)",
  entity: "var(--c-entity-soft)",
  goal: "var(--c-goal-soft)",
  constraint: "var(--c-constraint-soft)",
  decision: "var(--c-decision-soft)",
  open_question: "var(--c-question-soft)",
} as const;

/**
 * Pragmatic, hierarchical and state-link relations each get their own colour
 * within their group (see `HIER_COLOR`/`STATE_LINK_COLOR` below and
 * `edgeColor()`); mention and citation stay single-coloured since each is
 * only one relation type. Groups reuse each other's hues freely — a dash
 * pattern (`GROUP_DASH`) and, where relevant, curvature (`GROUP_CURVE`)
 * already distinguish one group from another, so colour only has to
 * disambiguate *within* a group, not across all of them at once.
 */
export const PRAGMATIC_COLOR: Record<string, string> = {
  revises: "var(--e-revises)",
  contradicts: "var(--e-contradicts)",
  resolves: "var(--e-resolves)",
  depends_on: "var(--e-dependson)",
  references: "var(--e-references)",
};

/** Hierarchical relations (subcase / supercase / same_level), same treatment
 *  as pragmatic — each gets its own colour rather than sharing `GROUP_COLOR`. */
export const HIER_COLOR: Record<string, string> = {
  subcase: "var(--e-hier-subcase)",
  supercase: "var(--e-hier-supercase)",
  same_level: "var(--e-hier-samelevel)",
};

/**
 * State-link relations. The backend emits three shapes of label for this
 * group (see `GraphStore._build` in `core/graph/graph_store.py`): the fixed
 * strings `"creates"` and `"updates -> {status}"` (status interpolated), and
 * a `StateRelation` value (`supports` / `contradicts` / `constrained_by` /
 * `resolves`) verbatim. `stateLinkBucket` normalises the first two so every
 * "updates -> X" reads as one colour regardless of which status X is —
 * colouring by the interpolated string would fragment into a near-duplicate
 * shade per status for no visual benefit.
 */
export const STATE_LINK_COLOR: Record<string, string> = {
  creates: "var(--e-state-creates)",
  updates: "var(--e-state-updates)",
  supports: "var(--e-state-supports)",
  contradicts: "var(--e-state-contradicts)",
  constrained_by: "var(--e-state-constrainedby)",
  resolves: "var(--e-state-resolves)",
};

function stateLinkBucket(label: string): string {
  return label.startsWith("updates") ? "updates" : label;
}

/** Used for the group-level filter chip swatch and as an unknown-label
 *  fallback; the actual rendered colour for hierarchical/pragmatic/state_link
 *  edges comes from their per-relation maps via `edgeColor()`. */
export const GROUP_COLOR: Record<EdgeGroup, string> = {
  hierarchical: "var(--e-hier)",
  pragmatic: "var(--e-dependson)",
  state_link: "var(--e-statelink)",
  citation: "var(--e-citation)",
  mention: "var(--e-mention)",
};

/** Dash patterns encode edge kind for readers who cannot rely on colour. */
export const GROUP_DASH: Record<EdgeGroup, string | undefined> = {
  hierarchical: "2,3",
  pragmatic: undefined, // solid: the relations that matter most read strongest
  state_link: "4,2",
  citation: "1,4",
  mention: "1,3",
};

/**
 * Perpendicular bow (px) applied to an edge's midpoint, quadratic-Bézier
 * style. Hierarchical, pragmatic and citation edges can all connect the same
 * pair of interaction nodes, so left straight they stack on top of each
 * other. Pragmatic stays at 0 — it is already the edge type meant to read
 * strongest — while hierarchical and citation bow to opposite sides, so a
 * pair carrying all three still shows three distinct lines. State-link and
 * mention edges reach entity/state nodes, a different pair-space that rarely
 * competes with these three, so they stay straight.
 */
export const GROUP_CURVE: Record<EdgeGroup, number> = {
  hierarchical: -10,
  pragmatic: 0,
  state_link: 0,
  citation: 12,
  mention: 0,
};

export function edgeColor(group: EdgeGroup, label: string): string {
  if (group === "pragmatic")
    return PRAGMATIC_COLOR[label] ?? PRAGMATIC_COLOR.references!;
  if (group === "hierarchical") return HIER_COLOR[label] ?? GROUP_COLOR.hierarchical;
  if (group === "state_link")
    return STATE_LINK_COLOR[stateLinkBucket(label)] ?? GROUP_COLOR.state_link;
  return GROUP_COLOR[group];
}

export const STATUS_STYLE: Record<
  EpistemicStatus | StateNodeStatus,
  { bg: string; fg: string }
> = {
  // EpistemicStatus values (section 3.5 of the Phase 1-2 report)
  open: { bg: "var(--c-question-soft)", fg: "var(--c-question)" },
  resolved: { bg: "var(--c-goal-soft)", fg: "var(--c-goal)" },
  contested: { bg: "var(--c-constraint-soft)", fg: "var(--c-constraint)" },
  superseded: { bg: "var(--c-entity-soft)", fg: "var(--c-entity)" },
  // StateNodeStatus values (section 3.3.1 of the Phase 1-2 report)
  active: { bg: "var(--c-goal-soft)", fg: "var(--c-goal)" },
  achieved: { bg: "var(--c-goal-soft)", fg: "var(--c-goal)" },
  abandoned: { bg: "var(--neutral-soft)", fg: "var(--ink-soft)" },
  revised: { bg: "var(--c-decision-soft)", fg: "var(--c-decision)" },
  reverted: { bg: "var(--neutral-soft)", fg: "var(--ink-soft)" },
  lifted: { bg: "var(--neutral-soft)", fg: "var(--ink-soft)" },
};

/** State nodes no longer in force are dimmed rather than hidden — the history
 *  is part of what the graph is for. Terminal statuses per section 3.3.1. */
export function isInactiveState(status: StateNodeStatus): boolean {
  return (
    status === "resolved" ||
    status === "abandoned" ||
    status === "reverted" ||
    status === "lifted" ||
    status === "achieved"
  );
}

export function stateNodeColor(type: StateNodeType) {
  return NODE_COLOR[type];
}
export function stateNodeFill(type: StateNodeType) {
  return NODE_FILL[type];
}

export const NODE_KIND_LABEL = {
  interaction: "Interaction",
  entity: "Entity",
  state: "State node",
} as const;

export const EDGE_GROUP_LABEL: Record<EdgeGroup, string> = {
  hierarchical: "Hierarchical",
  pragmatic: "Pragmatic",
  state_link: "State link",
  citation: "Citation",
  mention: "Mention",
};
