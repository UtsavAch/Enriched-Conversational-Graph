import { useEffect, useRef } from 'react';
import { axisBottom } from 'd3-axis';
import { select } from 'd3-selection';
import { timeFormat } from 'd3-time-format';
import type { ScaleTime } from 'd3-scale';

/**
 * The one place D3 is allowed to write to the DOM.
 *
 * Rendering a time axis by hand means reimplementing tick selection, which
 * `d3-axis` already does well. The exception is contained: the axis is a leaf,
 * has no React children, and lives in its own `<g>` that React never touches.
 * Documenting the exception is what stops it spreading.
 */
export function TimelineAxis({ scale, height }: { scale: ScaleTime<number, number>; height: number }) {
  const ref = useRef<SVGGElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    select(ref.current)
      .call(axisBottom(scale).ticks(6).tickFormat(timeFormat('%b %Y') as never));
  }, [scale]);

  return <g ref={ref} className="timeline-axis" transform={`translate(0,${height - 36})`} />;
}
