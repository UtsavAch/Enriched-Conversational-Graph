import { useEffect, useRef } from 'react';
import { useUiStore } from '@/store/uiStore';
import type { GraphView } from '@/types/api';
import { EmptyState } from '@/components/States';
import { Composer } from './Composer';
import { TurnCard } from './TurnCard';
import './ChatPanel.css';

/**
 * The conversation transcript.
 *
 * Two-way bound with the graph: clicking a turn selects its node, and selecting
 * a node scrolls its turn into view. That coupling is the point of the panel —
 * without it the graph is abstract and the transcript is unstructured, and
 * neither explains the other.
 */
export function ChatPanel({ graph, pendingQuestion }: {
  graph: GraphView | undefined;
  pendingQuestion: string | null;
}) {
  const selectedNodeId = useUiStore((s) => s.selectedNodeId);
  const selectNode = useUiStore((s) => s.selectNode);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLDivElement>(null);

  // Scroll the selected turn into view when selection comes from the graph.
  useEffect(() => {
    if (selectedNodeId && activeRef.current) {
      activeRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [selectedNodeId]);

  // Stay pinned to the bottom while a turn is being generated.
  useEffect(() => {
    if (pendingQuestion && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [pendingQuestion]);

  const turns = graph?.interaction_nodes ?? [];

  return (
    <aside className="chat-panel">
      <header className="chat-head">
        <h2 className="chat-title">{graph?.title ?? graph?.conversation_id ?? 'Conversation'}</h2>
        <p className="chat-sub">
          {graph
            ? `${turns.length} turn${turns.length === 1 ? '' : 's'} · schema ${graph.schema_version}`
            : 'no conversation loaded'}
        </p>
      </header>

      <div className="chat-scroll" ref={scrollRef}>
        {!graph ? (
          <EmptyState title="No conversation selected" hint="Pick one from the menu above, or create a new one." />
        ) : turns.length === 0 ? (
          <EmptyState title="No turns yet" hint="Send the first message to start building the memory graph." />
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
            {pendingQuestion && <TurnCard.Pending question={pendingQuestion} />}
          </>
        )}
      </div>

      <Composer />
    </aside>
  );
}
