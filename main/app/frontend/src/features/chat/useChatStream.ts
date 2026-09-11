import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { keys } from "@/api/queries";
import type { ChatResponse, ChatStreamPhase, GraphView } from "@/types/api";

export interface PendingTurn {
  question: string;
  phase: ChatStreamPhase;
  partialAnswer: string;
}

/**
 * Owns one streamed chat turn end to end.
 *
 * Posts to the SSE endpoint, tracks phase/partial-answer as events arrive,
 * and on `done` writes the final graph into the query cache exactly the way
 * the old non-streaming `useSendTurn` did in its `onSuccess` — everything
 * downstream of "the turn finished" (graph refetch, stats, conversation list)
 * behaves identically either way.
 *
 * `pending` is non-null for the whole span of one turn, including the
 * "updating_memory" tail after the answer text is already complete — the
 * composer stays disabled for that whole span (see `Composer`'s `disabled`
 * prop), matching the per-conversation lock the backend already holds for
 * the same span.
 */
export function useChatStream() {
  const qc = useQueryClient();
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [error, setError] = useState<string | null>(null);

  const send = useCallback(
    async (
      conversationId: string,
      question: string,
    ): Promise<string | undefined> => {
      setError(null);
      setPending({ question, phase: "thinking", partialAnswer: "" });

      try {
        let nodeId: string | undefined;

        for await (const evt of api.chat.turnStream(conversationId, question)) {
          if (evt.event === "answer_delta") {
            const { text } = JSON.parse(evt.data) as { text: string };
            setPending((p) =>
              p
                ? {
                    ...p,
                    phase: "generating_answer",
                    partialAnswer: p.partialAnswer + text,
                  }
                : p,
            );
          } else if (evt.event === "done") {
            const data = JSON.parse(evt.data) as ChatResponse;
            qc.setQueryData<GraphView>(keys.graph(conversationId), data.graph);
            qc.invalidateQueries({ queryKey: keys.graphStats(conversationId) });
            qc.invalidateQueries({ queryKey: keys.conversations });
            nodeId = data.turn?.node_id;
          } else if (evt.event === "error") {
            const data = JSON.parse(evt.data) as { detail?: string };
            throw new Error(data.detail || "The assistant failed to respond.");
          } else {
            // Any other event name is one of the coarse phase markers
            // ("thinking", "retrieving_context", "retrieving_documents",
            // "updating_memory") — see ChatStreamPhase.
            const phase = evt.event as ChatStreamPhase;
            setPending((p) => (p ? { ...p, phase } : p));
          }
        }

        setPending(null);
        return nodeId;
      } catch (err) {
        setPending(null);
        setError(err instanceof Error ? err.message : String(err));
        throw err;
      }
    },
    [qc],
  );

  return { send, pending, error };
}
