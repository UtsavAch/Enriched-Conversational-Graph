import { useEffect, useRef } from "react";
import { useUiStore } from "@/store/uiStore";
import type { GraphView } from "@/types/api";
import { EmptyState } from "@/components/States";
import { Composer } from "./Composer";
import { TurnCard } from "./TurnCard";
import { useChatStream } from "./useChatStream";
import "./ChatPanel.css";

/**
 * The conversation transcript.
 *
 * Two-way bound with the graph: clicking a turn selects its node, and selecting
 * a node scrolls its turn into view. That coupling is the point of the panel —
 * without it the graph is abstract and the transcript is unstructured, and
 * neither explains the other.
 *
 * Owns the streamed-turn state (`useChatStream`) and hands pieces of it to
 * `TurnCard.Pending` (to render) and `Composer` (to trigger and to know when
 * to disable itself) — the two things that need to agree on "is a turn in
 * flight right now" without either owning that state itself.
 */
export function ChatPanel({ graph }: { graph: GraphView | undefined }) {
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectNode = useUiStore((s) => s.selectNode);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLDivElement>(null);
  const { send, pending, error } = useChatStream();

  // Scroll the selected turn into view when selection comes from the graph.
  useEffect(() => {
    if (selectedNodeId && activeRef.current) {
      activeRef.current.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      });
    }
  }, [selectedNodeId]);

  // Stay pinned to the bottom while a turn streams in, including as the
  // answer text grows token by token.
  useEffect(() => {
    if (pending && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [pending]);

  const turns = graph?.interaction_nodes ?? [];

  return (
    <aside className="chat-panel">
      <header className="chat-head">
        <h2 className="chat-title">
          {graph?.title ?? graph?.conversation_id ?? "Conversation"}
        </h2>
        <p className="chat-sub">
          {graph
            ? `${turns.length} turn${turns.length === 1 ? "" : "s"} · schema ${graph.schema_version}`
            : "no conversation loaded"}
        </p>
      </header>

      <div className="chat-scroll" ref={scrollRef}>
        {!graph ? (
          <EmptyState
            title="No conversation selected"
            hint="Pick one from the menu above, or create a new one."
          />
        ) : turns.length === 0 && !pending ? (
          <EmptyState
            title="No turns yet"
            hint="Send the first message to start building the memory graph."
          />
        ) : (
          <>
            {turns.map((turn) => (
              <TurnCard
                key={turn.id}
                turn={turn}
                active={turn.id === selectedNodeId}
                onSelect={() => selectNode(turn.id)}
                ref={turn.id === selectedNodeId ? activeRef : undefined}
              />
            ))}
            {pending && (
              <TurnCard.Pending
                question={pending.question}
                phase={pending.phase}
                partialAnswer={pending.partialAnswer}
              />
            )}
          </>
        )}
      </div>

      <Composer
        streaming={Boolean(pending)}
        streamError={error}
        onSend={send}
      />
    </aside>
  );
}
