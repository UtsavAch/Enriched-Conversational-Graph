import { useRef } from "react";
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
import { EntitiesPanel } from "@/features/entities/EntitiesPanel";
import { StateNodesPanel } from "@/features/state-nodes/StateNodesPanel";
import { useResizableEdge } from "@/features/layout/useResizableEdge";
import { ResizeHandle } from "@/components/ResizeHandle";
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
  const chatExpandBy = useUiStore((s) => s.chatExpandBy);
  const panelExpandBy = useUiStore((s) => s.panelExpandBy);
  const setChatExpandBy = useUiStore((s) => s.setChatExpandBy);
  const setPanelExpandBy = useUiStore((s) => s.setPanelExpandBy);

  const health = useHealth();
  const graph = useGraph(conversationId);

  const workspaceRef = useRef<HTMLDivElement>(null);
  const chatFloatRef = useRef<HTMLDivElement>(null);
  const panelFloatRef = useRef<HTMLDivElement>(null);

  // Each panel's drag is clamped against the *other* panel's live width, so
  // the two floats can never overlap each other, however far either is
  // dragged — see useResizableEdge for the constraint itself.
  const chatResize = useResizableEdge({
    direction: 1,
    ownRef: chatFloatRef,
    otherRef: panelFloatRef,
    workspaceRef,
    expandBy: chatExpandBy,
    onChange: setChatExpandBy,
  });
  const panelResize = useResizableEdge({
    direction: -1,
    ownRef: panelFloatRef,
    otherRef: chatFloatRef,
    workspaceRef,
    expandBy: panelExpandBy,
    onChange: setPanelExpandBy,
  });

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

      <main className="workspace" ref={workspaceRef}>
        <div className="chat-spacer" aria-hidden />
        <div
          className={`chat-float${chatExpandBy > 0 ? " is-expanded" : ""}`}
          ref={chatFloatRef}
          style={{ width: `calc(var(--chat-width) + ${chatExpandBy}px)` }}
        >
          <ChatPanel graph={graph.data} />
          <ResizeHandle edge="right" onPointerDown={chatResize.onPointerDown} />
        </div>

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

        <div className="panel-spacer" aria-hidden />
        <div
          className={`panel-float${panelExpandBy > 0 ? " is-expanded" : ""}`}
          ref={panelFloatRef}
          style={{ width: `calc(var(--panel-width) + ${panelExpandBy}px)` }}
        >
          <ResizeHandle edge="left" onPointerDown={panelResize.onPointerDown} />
          <aside className="side-panel">
            <nav className="side-tabs" role="tablist">
              {(
                [
                  "inspector",
                  "entities",
                  "states",
                  "documents",
                  "health",
                ] as const
              ).map((tab) => (
                <button
                  key={tab}
                  role="tab"
                  aria-selected={sidePanel === tab}
                  className={sidePanel === tab ? "active" : ""}
                  onClick={() => setSidePanel(tab)}
                >
                  {tab === "inspector"
                    ? "Inspect"
                    : tab === "entities"
                      ? "Entities"
                      : tab === "states"
                        ? "States"
                        : tab === "documents"
                          ? "Documents"
                          : "Health"}
                </button>
              ))}
            </nav>

            <div className="side-body">
              {sidePanel === "inspector" && (
                <InspectorPanel graph={graph.data} />
              )}
              {sidePanel === "entities" && <EntitiesPanel graph={graph.data} />}
              {sidePanel === "states" && <StateNodesPanel graph={graph.data} />}
              {sidePanel === "documents" && (
                <DocumentsPanel conversationId={conversationId} />
              )}
              {sidePanel === "health" && <GraphHealthPanel />}
            </div>
          </aside>
        </div>
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
