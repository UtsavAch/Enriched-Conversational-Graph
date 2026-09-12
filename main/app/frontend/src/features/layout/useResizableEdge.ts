import { useCallback, useRef } from "react";

/**
 * Drag math for one side panel's resize handle.
 *
 * Deliberately does not touch layout itself — it only turns a pointer drag
 * into a clamped `expandBy` value (px past the panel's CSS default width) and
 * hands it to the caller's setter. Two constraints, both re-checked on every
 * pointer move so they hold even if the window is resized mid-drag:
 *
 * - A panel can only grow, never shrink below its current default.
 * - The two panels' floated widths may never exceed the workspace width minus
 *   `gap` — the amount of graph guaranteed to stay visible between them.
 */
export function useResizableEdge({
  direction,
  ownRef,
  otherRef,
  workspaceRef,
  expandBy,
  onChange,
  gap = 96,
}: {
  /** +1 for a panel that grows as the pointer moves right (the left/chat
   *  panel); -1 for one that grows as the pointer moves left (the right
   *  side panel). */
  direction: 1 | -1;
  ownRef: React.RefObject<HTMLElement>;
  otherRef: React.RefObject<HTMLElement>;
  workspaceRef: React.RefObject<HTMLElement>;
  expandBy: number;
  onChange: (px: number) => void;
  gap?: number;
}) {
  const drag = useRef<{
    startX: number;
    startWidth: number;
    defaultWidth: number;
  } | null>(null);

  const onPointerMove = useCallback(
    (e: PointerEvent) => {
      const d = drag.current;
      if (!d || !otherRef.current || !workspaceRef.current) return;

      const deltaX = (e.clientX - d.startX) * direction;
      // Anchored to where *this drag* started, not to the CSS default — a
      // panel already expanded from a previous drag must keep tracking the
      // pointer from its current width, not snap back to default first.
      let width = d.startWidth + deltaX;
      width = Math.max(width, d.defaultWidth);

      const otherWidth = otherRef.current.getBoundingClientRect().width;
      const workspaceWidth = workspaceRef.current.getBoundingClientRect().width;
      const maxWidth = Math.max(
        d.defaultWidth,
        workspaceWidth - otherWidth - gap,
      );
      width = Math.min(width, maxWidth);

      onChange(width - d.defaultWidth);
    },
    [direction, otherRef, workspaceRef, onChange, gap],
  );

  const stop = useCallback(() => {
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", stop);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    drag.current = null;
  }, [onPointerMove]);

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!ownRef.current) return;
      const rect = ownRef.current.getBoundingClientRect();
      drag.current = {
        startX: e.clientX,
        startWidth: rect.width,
        defaultWidth: rect.width - expandBy,
      };
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", stop);
      e.preventDefault();
    },
    [ownRef, expandBy, onPointerMove, stop],
  );

  return { onPointerDown };
}
