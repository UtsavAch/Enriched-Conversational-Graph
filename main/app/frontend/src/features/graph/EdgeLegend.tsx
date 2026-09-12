import {
  EDGE_GROUP_LABEL,
  GROUP_DASH,
  HIER_COLOR,
  PRAGMATIC_COLOR,
  STATE_LINK_COLOR,
} from "@/lib/graphStyles";
import type { EdgeGroup } from "@/types/api";
import "./EdgeLegend.css";

/** snake_case relation value -> readable label, e.g. "depends_on" -> "Depends on". */
function humanize(key: string): string {
  const [first, ...rest] = key.split("_");
  return [first!.charAt(0).toUpperCase() + first!.slice(1), ...rest].join(" ");
}

const LEGEND_GROUPS: { group: EdgeGroup; colors: Record<string, string> }[] = [
  { group: "hierarchical", colors: HIER_COLOR },
  { group: "pragmatic", colors: PRAGMATIC_COLOR },
  { group: "state_link", colors: STATE_LINK_COLOR },
];

/** A miniature of the real edge — same stroke colour, dash pattern and
 *  triangular arrowhead as the `<line>`/`<marker>` pair in `GraphCanvas` —
 *  so a legend entry previews exactly what that relation looks like on the
 *  graph, not just its colour. */
function ArrowSwatch({ color, dash }: { color: string; dash?: string }) {
  return (
    <svg
      className="edge-legend-arrow"
      width="20"
      height="10"
      viewBox="0 0 20 10"
      aria-hidden
    >
      <line
        x1="1"
        y1="5"
        x2="13"
        y2="5"
        stroke={color}
        strokeWidth="1.6"
        strokeDasharray={dash}
      />
      <path d="M12,1.5 L19,5 L12,8.5 Z" fill={color} />
    </svg>
  );
}

/**
 * Read-only key for the per-relation colours within each edge group, floated
 * over the top-right corner of the canvas (see `GraphCanvas`).
 *
 * Filtering stays on the group-level chips in `GraphToolbar`; this only
 * explains what a colour means once a group is switched on. Mention and
 * citation are single-relation groups, already fully explained by their own
 * toggle chip, so they are left out here.
 */
export function EdgeLegend() {
  return (
    <div className="edge-legend" aria-label="Edge colour legend">
      {LEGEND_GROUPS.map(({ group, colors }) => (
        <div className="edge-legend-group" key={group}>
          <span className="edge-legend-title">{EDGE_GROUP_LABEL[group]}</span>
          {Object.entries(colors).map(([relation, color]) => (
            <span className="edge-legend-item" key={relation}>
              <ArrowSwatch color={color} dash={GROUP_DASH[group]} />
              {humanize(relation)}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
