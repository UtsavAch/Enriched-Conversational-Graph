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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './endpoints';
import type { GraphView } from '@/types/api';

export const keys = {
  health: ['health'] as const,
  conversations: ['conversations'] as const,
  graph: (id: string) => ['graph', id] as const,
  graphStats: (id: string) => ['graph', id, 'stats'] as const,
  documents: ['documents'] as const,
  documentSearch: (q: string) => ['documents', 'search', q] as const,
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

export function useGraph(conversationId: string | null) {
  return useQuery({
    queryKey: keys.graph(conversationId ?? ''),
    queryFn: () => api.graph.get(conversationId!),
    enabled: Boolean(conversationId),
  });
}

export function useGraphStats(conversationId: string | null) {
  return useQuery({
    queryKey: keys.graphStats(conversationId ?? ''),
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
    mutationFn: ({ conversationId, question }: { conversationId: string; question: string }) =>
      api.chat.turn(conversationId, question),
    onSuccess: (data, vars) => {
      qc.setQueryData<GraphView>(keys.graph(vars.conversationId), data.graph);
      qc.invalidateQueries({ queryKey: keys.graphStats(vars.conversationId) });
      qc.invalidateQueries({ queryKey: keys.conversations });
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.documents.upload(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.documents }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => api.documents.remove(sourceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.documents }),
  });
}
