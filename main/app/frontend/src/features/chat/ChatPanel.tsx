import { useEffect, useRef, useState } from "react";
import { useConversations } from "@/api/queries";
import { useUiStore } from "@/store/uiStore";
import type { GraphView } from "@/types/api";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/States";
import { DeleteConversationDialog } from "@/features/conversations/DeleteConversationDialog";
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
  const setConversation = useUiStore((s) => s.setConversation);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLDivElement>(null);
  const { send, pending, error } = useChatStream();
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { data: conversations } = useConversations();
  const current =
    conversations?.find((c) => c.conversation_id === graph?.conversation_id) ??
    null;

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
        <div>
          <h2 className="chat-title">
            {graph?.title ?? graph?.conversation_id ?? "Conversation"}
          </h2>
          <p className="chat-sub">
            {graph
              ? `${turns.length} turn${turns.length === 1 ? "" : "s"} · schema ${graph.schema_version}`
              : "no conversation loaded"}
          </p>
        </div>

        <Button
          size="sm"
          variant="ghost"
          onClick={() => setDeleteOpen(true)}
          disabled={!graph}
        >
          Delete
        </Button>
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

      <DeleteConversationDialog
        conversation={deleteOpen ? current : null}
        onClose={() => setDeleteOpen(false)}
        onDeleted={() => {
          setDeleteOpen(false);
          // The deleted conversation can no longer be the active one.
          setConversation(null);
        }}
      />
    </aside>
  );
}
