/**
 * Typed wrappers around every backend route.
 *
 * One function per endpoint, each returning a typed result. Components never
 * build a URL, so renaming a route is a change here and nowhere else.
 */
import { http } from './client';
import type {
  ChatResponse, ConversationSummary, DocumentSearchHit, DocumentSource,
  GraphStats, GraphView, HealthResponse, NodeDetail,
} from '@/types/api';

const enc = encodeURIComponent;

export const api = {
  health: () => http.get<HealthResponse>('/api/health'),

  conversations: {
    list: () => http.get<ConversationSummary[]>('/api/conversations'),
    remove: (id: string) => http.delete<{ deleted: string }>(`/api/conversations/${enc(id)}`),
  },

  graph: {
    get: (id: string) => http.get<GraphView>(`/api/graph/${enc(id)}`),
    node: (id: string, nodeId: string) =>
      http.get<NodeDetail>(`/api/graph/${enc(id)}/node/${enc(nodeId)}`),
    stats: (id: string) => http.get<GraphStats>(`/api/graph/${enc(id)}/stats`),
  },

  chat: {
    /** `answer` is only supplied when ingesting an existing turn. */
    turn: (conversation_id: string, question: string, answer?: string) =>
      http.post<ChatResponse>('/api/chat/turn', { conversation_id, question, answer }),
  },

  documents: {
    list: () => http.get<DocumentSource[]>('/api/documents'),
    upload: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return http.upload<DocumentSource>('/api/documents/upload', form);
    },
    search: (q: string, k = 5) =>
      http.get<DocumentSearchHit[]>(`/api/documents/search?q=${enc(q)}&k=${k}`),
    remove: (sourceId: string) =>
      http.delete<{ deleted: string }>(`/api/documents/${enc(sourceId)}`),
  },
};
