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
import type { EdgeGroup, EpistemicStatus, StateNodeStatus, StateNodeType } from '@/types/api';

export const NODE_COLOR = {
  interaction: 'var(--c-interaction)',
  entity: 'var(--c-entity)',
  goal: 'var(--c-goal)',
  constraint: 'var(--c-constraint)',
  decision: 'var(--c-decision)',
  open_question: 'var(--c-question)',
} as const;

export const NODE_FILL = {
  interaction: 'var(--c-interaction-soft)',
  entity: 'var(--c-entity-soft)',
  goal: 'var(--c-goal-soft)',
  constraint: 'var(--c-constraint-soft)',
  decision: 'var(--c-decision-soft)',
  open_question: 'var(--c-question-soft)',
} as const;

/**
 * Pragmatic relations each get their own colour; the other groups share one.
 * That asymmetry is deliberate — the pragmatic relations are the contribution
 * of this work, so they carry the visual distinction. Mentions and citations
 * are derived, not classified, and are styled to recede.
 */
export const PRAGMATIC_COLOR: Record<string, string> = {
  revises: 'var(--e-revises)',
  contradicts: 'var(--e-contradicts)',
  resolves: 'var(--e-resolves)',
  depends_on: 'var(--e-dependson)',
  references: 'var(--e-references)',
};

export const GROUP_COLOR: Record<EdgeGroup, string> = {
  hierarchical: 'var(--e-hier)',
  pragmatic: 'var(--e-dependson)', // only a legend fallback; see edgeColor()
  state_link: 'var(--e-statelink)',
  citation: 'var(--e-citation)',
  mention: 'var(--e-mention)',
};

/** Dash patterns encode edge kind for readers who cannot rely on colour. */
export const GROUP_DASH: Record<EdgeGroup, string | undefined> = {
  hierarchical: '2,3',
  pragmatic: undefined, // solid: the relations that matter most read strongest
  state_link: '4,2',
  citation: '1,4',
  mention: '1,3',
};

export function edgeColor(group: EdgeGroup, label: string): string {
  if (group === 'pragmatic') return PRAGMATIC_COLOR[label] ?? PRAGMATIC_COLOR.references!;
  return GROUP_COLOR[group];
}

export const STATUS_STYLE: Record<
  EpistemicStatus | StateNodeStatus,
  { bg: string; fg: string }
> = {
  open:       { bg: 'var(--c-question-soft)',    fg: 'var(--c-question)' },
  resolved:   { bg: 'var(--c-goal-soft)',        fg: 'var(--c-goal)' },
  contested:  { bg: 'var(--c-constraint-soft)',  fg: 'var(--c-constraint)' },
  superseded: { bg: 'var(--c-entity-soft)',      fg: 'var(--c-entity)' },
  active:     { bg: 'var(--c-goal-soft)',        fg: 'var(--c-goal)' },
  revised:    { bg: 'var(--c-decision-soft)',    fg: 'var(--c-decision)' },
  achieved:   { bg: 'var(--c-goal-soft)',        fg: 'var(--c-goal)' },
  abandoned:  { bg: 'var(--neutral-soft)',       fg: 'var(--ink-soft)' },
  satisfied:  { bg: 'var(--c-goal-soft)',        fg: 'var(--c-goal)' },
  violated:   { bg: 'var(--c-constraint-soft)',  fg: 'var(--c-constraint)' },
};

/** State nodes no longer in force are dimmed rather than hidden — the history
 *  is part of what the graph is for. */
export function isInactiveState(status: StateNodeStatus): boolean {
  return status === 'resolved' || status === 'revised'
      || status === 'superseded' || status === 'abandoned';
}

export function stateNodeColor(type: StateNodeType) { return NODE_COLOR[type]; }
export function stateNodeFill(type: StateNodeType) { return NODE_FILL[type]; }

export const NODE_KIND_LABEL = {
  interaction: 'Interaction',
  entity: 'Entity',
  state: 'State node',
} as const;

export const EDGE_GROUP_LABEL: Record<EdgeGroup, string> = {
  hierarchical: 'Hierarchical',
  pragmatic: 'Pragmatic',
  state_link: 'State link',
  citation: 'Citation',
  mention: 'Mention',
};
