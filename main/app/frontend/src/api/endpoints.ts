/**
 * Typed wrappers around every backend route.
 *
 * One function per endpoint, each returning a typed result. Components never
 * build a URL, so renaming a route is a change here and nowhere else.
 */
import { http } from "./client";
import type {
  ChatResponse,
  ConversationSummary,
  DocumentSearchHit,
  DocumentSource,
  GraphStats,
  GraphView,
  HealthResponse,
  NodeDetail,
} from "@/types/api";

const enc = encodeURIComponent;

export const api = {
  health: () => http.get<HealthResponse>("/api/health"),

  conversations: {
    list: () => http.get<ConversationSummary[]>("/api/conversations"),
    /** Creates an empty conversation from a topic — no first turn, no id to
     *  invent: the backend slugifies `title` into a unique id and returns it.
     *  Send the first message separately via `chat.turn`, once documents (if
     *  any) have been scoped to it. */
    create: (title: string) =>
      http.post<{ conversation_id: string; title: string | null }>(
        "/api/conversations",
        { title },
      ),
    remove: (id: string) =>
      http.delete<{ deleted: string }>(`/api/conversations/${enc(id)}`),
    documents: {
      /** Documents this conversation's retrieval is scoped to (uploaded or
       *  selected). Empty means "no explicit scope" — retrieval falls back to
       *  searching every document, not "nothing is available to it". */
      list: (id: string) =>
        http.get<DocumentSource[]>(`/api/conversations/${enc(id)}/documents`),
      /** Scope this conversation's retrieval to include an already-ingested
       *  document, without re-uploading it. */
      select: (id: string, sourceId: string) =>
        http.post<{ selected: string }>(
          `/api/conversations/${enc(id)}/documents/${enc(sourceId)}`,
        ),
      deselect: (id: string, sourceId: string) =>
        http.delete<{ deselected: string }>(
          `/api/conversations/${enc(id)}/documents/${enc(sourceId)}`,
        ),
    },
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
      http.post<ChatResponse>("/api/chat/turn", {
        conversation_id,
        question,
        answer,
      }),
  },

  documents: {
    list: () => http.get<DocumentSource[]>("/api/documents"),
    /** `conversationId`, when given, both archives a copy of the file into
     *  that conversation's `documents/` folder AND scopes that conversation's
     *  retrieval to include it (see `conversations.documents`). */
    upload: (file: File, conversationId?: string | null) => {
      const form = new FormData();
      form.append("file", file);
      if (conversationId) form.append("conversation_id", conversationId);
      return http.upload<DocumentSource>("/api/documents/upload", form);
    },
    search: (q: string, k = 5) =>
      http.get<DocumentSearchHit[]>(`/api/documents/search?q=${enc(q)}&k=${k}`),
    remove: (sourceId: string) =>
      http.delete<{ deleted: string }>(`/api/documents/${enc(sourceId)}`),
  },
};
