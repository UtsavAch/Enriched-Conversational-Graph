import { useEffect, useRef } from "react";
import { axisBottom } from "d3-axis";
import { select } from "d3-selection";
import type { ScaleTime } from "d3-scale";

/**
 * The one place D3 is allowed to write to the DOM.
 *
 * Rendering a time axis by hand means reimplementing tick selection, which
 * `d3-axis` already does well. The exception is contained: the axis is a leaf,
 * has no React children, and lives in its own `<g>` that React never touches.
 * Documenting the exception is what stops it spreading.
 */
export function TimelineAxis({
  scale,
  height,
}: {
  scale: ScaleTime<number, number>;
  height: number;
}) {
  const ref = useRef<SVGGElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    // No explicit tickFormat: `axisBottom` falls back to the scale's own
    // adaptive formatter, which switches resolution (time-of-day, day,
    // month, year) to match how far apart the ticks actually are — a
    // same-day conversation reads as clock times, a multi-year one as
    // years, with no manual format-switching needed.
    select(ref.current).call(axisBottom(scale).ticks(6));
  }, [scale]);

  return (
    <g
      ref={ref}
      className="timeline-axis"
      transform={`translate(0,${height - 36})`}
    />
  );
}
