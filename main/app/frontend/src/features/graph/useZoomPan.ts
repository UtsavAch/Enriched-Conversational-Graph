/**
 * Zoom and pan.
 *
 * d3-zoom handles the gesture maths (wheel normalisation across trackpads and
 * mice, pinch, momentum) — reimplementing that is a bad use of time. But the
 * resulting transform is applied by React to a `<g>` element, not written to
 * the DOM by D3, keeping the ownership boundary intact.
 */
import { useEffect, useRef, useState } from 'react';
import { select } from 'd3-selection';
// Imported for its side effect: d3-transition augments the Selection type with
// .transition(). Without it the smooth reset below does not typecheck.
import 'd3-transition';
import { zoom, zoomIdentity, type ZoomTransform } from 'd3-zoom';

export function useZoomPan(svgRef: React.RefObject<SVGSVGElement>) {
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity);
  const behaviorRef = useRef<ReturnType<typeof zoom<SVGSVGElement, unknown>> | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;

    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      // Without this, starting a node drag would also pan the canvas. Node
      // drags set their own handlers and stop propagation, but blocking the
      // zoom on non-primary buttons avoids surprises with middle-click too.
      .filter((event) => !event.ctrlKey && !event.button)
      .on('zoom', (event) => setTransform(event.transform));

    select(svg).call(behavior);
    behaviorRef.current = behavior;

    return () => { select(svg).on('.zoom', null); };
  }, [svgRef]);

  const reset = () => {
    const svg = svgRef.current;
    if (!svg || !behaviorRef.current) return;
    select(svg).transition().duration(350).call(behaviorRef.current.transform, zoomIdentity);
  };

  return { transform, reset };
}
