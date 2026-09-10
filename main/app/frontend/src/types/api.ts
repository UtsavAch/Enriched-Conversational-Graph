/**
 * Types mirroring the backend schema.
 *
 * These are hand-written rather than generated, and the trade-off is worth
 * stating: generation from the OpenAPI schema would guarantee they never drift,
 * but it adds a build step and produces names nobody wants to read. Hand-written
 * types stay readable and are checked in one place — `tests/test_app_view_model.py`
 * asserts the exact field names the frontend reads, so a backend change that
 * breaks this file fails a Python test rather than silently rendering wrong.
 *
 * Source of truth: `app/backend/view_model.py`.
 */

// ── controlled vocabularies (mirror core/schema/enums.py) ──────────────────

export type NodeKind = "interaction" | "entity" | "state";

export type SpeechAct =
  | "factual_question"
  | "clarification_request"
  | "decision"
  | "suggestion"
  | "feedback"
  | "correction"
  | "follow_up"
  | "agreement"
  | "disagreement"
  | "information"
  | "request";

export type EpistemicStatus = "open" | "resolved" | "contested" | "superseded";

export type StateNodeType =
  | "goal"
  | "decision"
  | "constraint"
  | "open_question";

export type StateNodeStatus =
  | "active" // goal, decision, constraint: starting status
  | "open" // open_question: starting status
  | "achieved" // goal: terminal
  | "abandoned" // goal: terminal
  | "revised" // decision, constraint: non-terminal (can repeat)
  | "reverted" // decision: terminal
  | "lifted" // constraint: terminal
  | "resolved"; // open_question: terminal

export type EntityType =
  | "person"
  | "organization"
  | "system"
  | "location"
  | "document"
  | "tool"
  | "event"
  | "measurement"
  | "other";

/**
 * Edge groups. `mention` and `citation` are derived rather than classified —
 * they carry no discourse meaning and are filtered out of graph expansion by
 * default on the backend.
 */
export type EdgeGroup =
  | "hierarchical"
  | "pragmatic"
  | "state_link"
  | "citation"
  | "mention";

export type PragmaticRelation =
  | "revises"
  | "contradicts"
  | "resolves"
  | "depends_on"
  | "references";

// ── view model (mirrors build_graph_view) ─────────────────────────────────

/** One entry in a node's epistemic audit trail: [caused_by, trigger, status]. */
export type EpistemicEvent = [string, string, EpistemicStatus];

export interface InteractionNodeView {
  id: string;
  timestamp: string;
  turn_index: number;
  question: string;
  answer: string;
  summary: string;
  reference: string;
  speech_act: SpeechAct;
  epistemic_status: EpistemicStatus;
  recurrence_count: number;
  retrieval_count: number;
  named_entities: string[];
  citations: string[];
  /**
   * Document chunk ids that grounded this answer. Deliberately a flat
   * provenance list, not a graph edge — see ADR-002. The UI renders it as a
   * distinct affordance so that separation stays visible.
   */
  grounded_by: string[];
  epistemic_history: EpistemicEvent[];
}

export interface EntityView {
  id: string;
  type: EntityType;
  name: string;
  mentioned_in: string[];
  timestamp: string;
}

export interface StateNodeView {
  id: string;
  type: StateNodeType;
  label: string;
  status: StateNodeStatus;
  creation_turn: string;
  last_updated_turn: string;
  timestamp: string;
}

export interface EdgeView {
  source: string;
  target: string;
  label: string;
  group: EdgeGroup;
}

export interface GraphView {
  conversation_id: string;
  title: string | null;
  schema_version: string;
  interaction_nodes: InteractionNodeView[];
  entities: EntityView[];
  state_nodes: StateNodeView[];
  edges: EdgeView[];
  stats: Record<string, number>;
}

// ── other endpoints ────────────────────────────────────────────────────────

export interface ConversationSummary {
  conversation_id: string;
  title: string | null;
  source: string | null;
  n_turns: number;
  n_entities: number;
  n_state_nodes: number;
  updated_at: string;
}

export interface RelationRef {
  direction: "in" | "out";
  other: string;
  other_name: string;
  label: string;
  group: EdgeGroup;
  strength: number;
}

export interface NodeDetail {
  id: string;
  kind: NodeKind;
  node: Record<string, unknown>;
  relations: RelationRef[];
}

/**
 * Graph health diagnostics. Worth watching during Phase 3 validation: a
 * relation type with a near-zero count, or a graph that fragments into many
 * components, are findings about the classifier or the corpus.
 */
export interface GraphStats {
  counts: Record<string, number>;
  n_components: number;
  largest_component: number;
  isolated_nodes: string[];
  dangling_references: string[];
}

export interface HealthResponse {
  status: string;
  version: string;
  chat_enabled: boolean;
}

export interface DocumentSource {
  id: string;
  title: string;
  source_type: string;
  uri: string;
  n_chunks: number;
  ingested_at: string;
  metadata: Record<string, string>;
}

export interface DocumentSearchHit {
  chunk_id: string;
  source_id: string;
  source_title: string;
  page: number | null;
  score: number;
  text: string;
}

export interface TurnSummary {
  node_id: string;
  speech_act: string;
  n_hierarchical: number;
  n_pragmatic: number;
  n_entities: number;
  n_state_created: number;
  context: Record<string, number>;
  /** The bounded-per-turn-cost audit record. Surfaced in the UI on purpose. */
  cost: {
    turn_id: string;
    n_calls: number;
    n_failed: number;
    input_tokens: number;
    output_tokens: number;
    wall_clock_s: number;
    serial_s: number;
  };
  errors: string[];
}

export interface ChatResponse {
  answer: string;
  turn: TurnSummary;
  graph: GraphView;
}

// ── graph rendering (client-side only) ────────────────────────────────────

/**
 * The unified node the graph renders. Discriminated union on `kind` so that
 * TypeScript narrows `data` correctly in the inspector — this is what stops
 * `d.label` being read off an interaction node.
 */
export type GraphNodeDatum =
  | { id: string; kind: "interaction"; data: InteractionNodeView }
  | { id: string; kind: "entity"; data: EntityView }
  | { id: string; kind: "state"; data: StateNodeView };
