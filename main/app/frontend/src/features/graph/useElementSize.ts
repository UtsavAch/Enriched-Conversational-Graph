/**
 * Measure an element, and keep measuring as it changes.
 *
 * The force simulation needs real pixel dimensions to centre itself, and the
 * canvas is a flex child whose size depends on the panels around it. A
 * `ResizeObserver` is the only way to know that reliably — window `resize`
 * misses layout changes such as a side panel opening.
 */
import { useEffect, useState, type RefObject } from 'react';

export function useElementSize(ref: RefObject<Element>) {
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      // Round to whole pixels: sub-pixel changes would otherwise restart the
      // simulation on every scrollbar flicker.
      setSize((prev) =>
        Math.round(prev.width) === Math.round(width) &&
        Math.round(prev.height) === Math.round(height)
          ? prev
          : { width, height },
      );
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);

  return size;
}
