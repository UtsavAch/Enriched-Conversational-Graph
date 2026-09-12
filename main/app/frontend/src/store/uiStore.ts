/**
 * UI state — everything that is *not* server data.
 *
 * The split matters. Server state (graphs, conversations, documents) is owned
 * by TanStack Query: it is cached, refetched, and invalidated. UI state
 * (what is selected, which filters are on, which panel is open) is owned here:
 * it is synchronous, local, and never refetched.
 *
 * Conflating the two is the usual way a frontend like this becomes hard to
 * change — you end up refetching a graph because a filter toggled.
 *
 * Zustand rather than Context because the graph canvas reads selection state on
 * every frame. Context re-renders every consumer on any change; Zustand's
 * selector subscriptions mean a filter toggle does not re-render the inspector.
 */
import { create } from "zustand";
import type { EdgeGroup, NodeKind } from "@/types/api";

export type ViewMode = "graph" | "timeline";
export type SidePanel =
  | "inspector"
  | "documents"
  | "health"
  | "entities"
  | "states";

interface UiState {
  conversationId: string | null;
  selectedNodeId: string | null;
  viewMode: ViewMode;
  sidePanel: SidePanel;
  nodeFilters: Record<NodeKind, boolean>;
  edgeFilters: Record<EdgeGroup, boolean>;
  /** How far each side panel is dragged past its CSS default width, in px.
   *  0 means "default size" — the panels' actual default width lives in
   *  `--chat-width`/`--panel-width` (tokens.css), not here. Not persisted:
   *  like `sidePanel`/`viewMode`, this resets on reload. */
  chatExpandBy: number;
  panelExpandBy: number;

  setConversation: (id: string | null) => void;
  selectNode: (id: string | null) => void;
  setViewMode: (m: ViewMode) => void;
  setSidePanel: (p: SidePanel) => void;
  toggleNodeFilter: (k: NodeKind) => void;
  toggleEdgeFilter: (g: EdgeGroup) => void;
  setChatExpandBy: (px: number) => void;
  setPanelExpandBy: (px: number) => void;
}

/** Restored on load so a refresh does not lose the open conversation. */
const LAST_CONVERSATION_KEY = "gm:lastConversation";

function readInitialConversation(): string | null {
  // The URL wins over storage, so a shared link always opens what it names.
  const fromUrl = new URLSearchParams(window.location.search).get(
    "conversation",
  );
  if (fromUrl) return fromUrl;
  try {
    return localStorage.getItem(LAST_CONVERSATION_KEY);
  } catch {
    return null;
  }
}

function persistConversation(id: string | null) {
  try {
    if (id) localStorage.setItem(LAST_CONVERSATION_KEY, id);
    else localStorage.removeItem(LAST_CONVERSATION_KEY);
  } catch {
    /* private browsing — not worth failing over */
  }

  const url = new URL(window.location.href);
  if (id) url.searchParams.set("conversation", id);
  else url.searchParams.delete("conversation");
  window.history.replaceState(null, "", url);
}

export const useUiStore = create<UiState>((set) => ({
  conversationId: readInitialConversation(),
  selectedNodeId: null,
  viewMode: "graph",
  sidePanel: "inspector",
  nodeFilters: { interaction: true, entity: true, state: true },
  edgeFilters: {
    hierarchical: true,
    pragmatic: true,
    state_link: true,
    citation: true,
    mention: true,
  },
  chatExpandBy: 0,
  panelExpandBy: 0,

  setConversation: (id) => {
    persistConversation(id);
    // Selection is cleared: a node id from one conversation is meaningless in
    // another, and keeping it would leave the inspector showing a stale node.
    set({ conversationId: id, selectedNodeId: null });
  },

  selectNode: (id) => set({ selectedNodeId: id, sidePanel: "inspector" }),
  setViewMode: (viewMode) => set({ viewMode }),
  setSidePanel: (sidePanel) => set({ sidePanel }),

  toggleNodeFilter: (k) =>
    set((s) => ({ nodeFilters: { ...s.nodeFilters, [k]: !s.nodeFilters[k] } })),
  toggleEdgeFilter: (g) =>
    set((s) => ({ edgeFilters: { ...s.edgeFilters, [g]: !s.edgeFilters[g] } })),

  setChatExpandBy: (px) => set({ chatExpandBy: px }),
  setPanelExpandBy: (px) => set({ panelExpandBy: px }),
}));
