import { useGraph, useHealth } from "@/api/queries";
import { useUiStore } from "@/store/uiStore";
import { ApiError } from "@/api/client";
import { ConversationPicker } from "@/features/conversations/ConversationPicker";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { GraphCanvas } from "@/features/graph/GraphCanvas";
import { GraphToolbar } from "@/features/graph/GraphToolbar";
import { InspectorPanel } from "@/features/inspector/InspectorPanel";
import { DocumentsPanel } from "@/features/documents/DocumentsPanel";
import { GraphHealthPanel } from "@/features/health/GraphHealthPanel";
import { EmptyState, ErrorState, Spinner } from "@/components/States";
import "./App.css";

/**
 * Application shell.
 *
 * Three regions: the transcript on the left, the graph in the middle, an
 * inspector on the right. That arrangement is the argument the app is making —
 * the dialogue and its structure are two views of the same thing, and the
 * inspector explains any point where they meet.
 */
export default function App() {
  const conversationId = useUiStore((s) => s.conversationId);
  const sidePanel = useUiStore((s) => s.sidePanel);
  const setSidePanel = useUiStore((s) => s.setSidePanel);

  const health = useHealth();
  const graph = useGraph(conversationId);

  // The server being unreachable is the one failure worth taking over the whole
  // screen: nothing else in the app can work, and the fix is a shell command.
  if (health.isError) {
    return (
      <div className="app-shell">
        <ErrorState
          title="Cannot reach the server"
          detail={
            "Start the backend, then reload:\n\n  uvicorn app.backend.main:app --reload"
          }
          onRetry={() => health.refetch()}
        />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="app-title">Conversational Memory Graph</h1>
        <ConversationPicker />

        {graph.data && (
          <dl className="app-stats">
            <Stat
              label="interactions"
              value={graph.data.interaction_nodes.length}
            />
            <Stat label="entities" value={graph.data.entities.length} />
            <Stat label="state nodes" value={graph.data.state_nodes.length} />
            <Stat label="edges" value={graph.data.edges.length} />
          </dl>
        )}
      </header>

      <GraphToolbar />

      <main className="workspace">
        <ChatPanel graph={graph.data} pendingQuestion={null} />

        {!conversationId ? (
          <div className="canvas-placeholder">
            <EmptyState
              title="No conversation open"
              hint="Choose one from the menu above to see its memory graph, or build one from a transcript with scripts/ingest_conversation.py."
            />
          </div>
        ) : graph.isLoading ? (
          <div className="canvas-placeholder">
            <Spinner label="Loading graph…" />
          </div>
        ) : graph.isError ? (
          <div className="canvas-placeholder">
            <ErrorState
              title={
                (graph.error as ApiError).isNotFound
                  ? `No conversation named "${conversationId}"`
                  : "Could not load the graph"
              }
              detail={(graph.error as ApiError).detail}
              onRetry={() => graph.refetch()}
            />
          </div>
        ) : graph.data && graph.data.interaction_nodes.length === 0 ? (
          <div className="canvas-placeholder">
            <EmptyState
              title="This conversation is empty"
              hint="Send a message to build the first node."
            />
          </div>
        ) : (
          <GraphCanvas graph={graph.data!} />
        )}

        <aside className="side-panel">
          <nav className="side-tabs" role="tablist">
            {(["inspector", "documents", "health"] as const).map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={sidePanel === tab}
                className={sidePanel === tab ? "active" : ""}
                onClick={() => setSidePanel(tab)}
              >
                {tab === "inspector"
                  ? "Inspect"
                  : tab === "documents"
                    ? "Documents"
                    : "Health"}
              </button>
            ))}
          </nav>

          <div className="side-body">
            {sidePanel === "inspector" && <InspectorPanel graph={graph.data} />}
            {sidePanel === "documents" && (
              <DocumentsPanel conversationId={conversationId} />
            )}
            {sidePanel === "health" && <GraphHealthPanel />}
          </div>
        </aside>
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat">
      <dt className="stat-label">{label}</dt>
      <dd className="stat-value">{value}</dd>
    </div>
  );
}
