/**
 * TanStack Query hooks — the server-state layer.
 *
 * Why a query library rather than useEffect + useState:
 *
 * - **Caching and deduplication.** The conversation list is read by the picker
 *   and by the new-conversation dialog. Without a cache that is two requests
 *   and two chances to disagree.
 * - **Invalidation as the update mechanism.** Posting a turn invalidates the
 *   graph query; every component showing graph data refetches. No manual
 *   "also update the stats" wiring, which is where this kind of app usually
 *   starts to rot.
 * - **Loading and error states for free**, consistently, in every consumer.
 *
 * Query keys are hierarchical (`['graph', id]`) so that invalidating `['graph']`
 * clears every conversation at once when that is what is wanted.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./endpoints";
import type { GraphView } from "@/types/api";

export const keys = {
  health: ["health"] as const,
  conversations: ["conversations"] as const,
  graph: (id: string) => ["graph", id] as const,
  graphStats: (id: string) => ["graph", id, "stats"] as const,
  documents: ["documents"] as const,
  documentSearch: (q: string) => ["documents", "search", q] as const,
  conversationDocuments: (id: string) =>
    ["conversations", id, "documents"] as const,
};

/** Server capabilities. Determines whether the composer is usable. */
export function useHealth() {
  return useQuery({
    queryKey: keys.health,
    queryFn: api.health,
    staleTime: Infinity, // capabilities do not change while the page is open
    retry: 1,
  });
}

export function useConversations() {
  return useQuery({
    queryKey: keys.conversations,
    queryFn: api.conversations.list,
  });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (title: string) => api.conversations.create(title),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.conversations }),
  });
}

/**
 * Delete a conversation. The backend removes its whole directory in one go
 * (interactions, entities, state nodes, its documents folder — everything),
 * so the only cleanup needed here is dropping now-meaningless cached queries
 * for that id, rather than leaving them to be refetched into 404s.
 */
export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.conversations.remove(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: keys.conversations });
      qc.removeQueries({ queryKey: keys.graph(id) });
      qc.removeQueries({ queryKey: keys.graphStats(id) });
      qc.removeQueries({ queryKey: keys.conversationDocuments(id) });
    },
  });
}

export function useGraph(conversationId: string | null) {
  return useQuery({
    queryKey: keys.graph(conversationId ?? ""),
    queryFn: () => api.graph.get(conversationId!),
    enabled: Boolean(conversationId),
  });
}

export function useGraphStats(conversationId: string | null) {
  return useQuery({
    queryKey: keys.graphStats(conversationId ?? ""),
    queryFn: () => api.graph.stats(conversationId!),
    enabled: Boolean(conversationId),
  });
}

export function useDocuments() {
  return useQuery({ queryKey: keys.documents, queryFn: api.documents.list });
}

export function useDocumentSearch(query: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.documentSearch(query),
    queryFn: () => api.documents.search(query),
    enabled: enabled && query.trim().length > 0,
  });
}

/**
 * Send a turn.
 *
 * The response already contains the full updated graph, so it is written
 * straight into the cache with `setQueryData` rather than triggering a refetch.
 * That removes a round trip and, more importantly, removes the window in which
 * the chat panel shows the new turn but the graph does not.
 */
export function useSendTurn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      conversationId,
      question,
    }: {
      conversationId: string;
      question: string;
    }) => api.chat.turn(conversationId, question),
    onSuccess: (data, vars) => {
      qc.setQueryData<GraphView>(keys.graph(vars.conversationId), data.graph);
      qc.invalidateQueries({ queryKey: keys.graphStats(vars.conversationId) });
      qc.invalidateQueries({ queryKey: keys.conversations });
    },
  });
}

export function useUploadDocument(conversationId?: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.documents.upload(file, conversationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.documents });
      // Uploading through a conversation also scopes that conversation's
      // retrieval to the new document (see the backend's attach step) — keep
      // the selection list in sync so it shows up as selected immediately.
      if (conversationId) {
        qc.invalidateQueries({
          queryKey: keys.conversationDocuments(conversationId),
        });
      }
    },
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => api.documents.remove(sourceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.documents }),
  });
}

/** Documents the given conversation's retrieval is currently scoped to. */
export function useConversationDocuments(conversationId: string | null) {
  return useQuery({
    queryKey: keys.conversationDocuments(conversationId ?? ""),
    queryFn: () => api.conversations.documents.list(conversationId!),
    enabled: Boolean(conversationId),
  });
}

export function useSelectConversationDocument(conversationId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) =>
      api.conversations.documents.select(conversationId!, sourceId),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: keys.conversationDocuments(conversationId ?? ""),
      }),
  });
}

export function useDeselectConversationDocument(conversationId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) =>
      api.conversations.documents.deselect(conversationId!, sourceId),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: keys.conversationDocuments(conversationId ?? ""),
      }),
  });
}
