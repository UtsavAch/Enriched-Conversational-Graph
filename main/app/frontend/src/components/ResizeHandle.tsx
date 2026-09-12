import "./ResizeHandle.css";

/** A thin draggable strip on a floated side panel's inner edge. Purely
 *  presentational — the drag math lives in `useResizableEdge`. */
export function ResizeHandle({
  edge,
  onPointerDown,
}: {
  edge: "left" | "right";
  onPointerDown: (e: React.PointerEvent) => void;
}) {
  return (
    <div
      className={`resize-handle resize-handle-${edge}`}
      onPointerDown={onPointerDown}
      role="separator"
      aria-orientation="vertical"
    />
  );
}
