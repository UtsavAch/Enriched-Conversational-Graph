import { useGraphStats } from '@/api/queries';
import { useUiStore } from '@/store/uiStore';
import { Spinner, EmptyState } from '@/components/States';
import { edgeColor } from '@/lib/graphStyles';
import './Health.css';

/**
 * Graph health diagnostics.
 *
 * Built for Phase 3 validation rather than for demos. Three things here are
 * findings, not decoration:
 *
 * - **A relation type with a near-zero count.** The baseline thesis found
 *   `supercase` fired in 4 of 3,954 edges on LoCoMo. If a pragmatic relation
 *   shows the same pattern on your corpus, that is evidence about either the
 *   corpus or the prompt, and it is worth seeing before running any metric.
 * - **Many components.** A graph that fragments means the classifier is
 *   emitting `no_relation` too freely — the thinness problem.
 * - **Dangling references.** Best-effort extraction can leave an edge pointing
 *   at a node that was never created. Silent until it breaks traversal.
 */
export function GraphHealthPanel() {
  const conversationId = useUiStore((s) => s.conversationId);
  const selectNode = useUiStore((s) => s.selectNode);
  const { data: stats, isLoading } = useGraphStats(conversationId);

  if (!conversationId) return <EmptyState title="No conversation selected" />;
  if (isLoading) return <Spinner label="Computing…" />;
  if (!stats) return <EmptyState title="No statistics available" />;

  // Split the flat counts map into per-relation rows, dropping the group totals.
  const relationRows = Object.entries(stats.counts)
    .filter(([k]) => k.includes(':') && !k.startsWith('nodes:'))
    .map(([k, count]) => {
      const [group = '', label = ''] = k.split(':');
      return { group, label, count };
    })
    .sort((a, b) => b.count - a.count);

  const fragmented = stats.n_components > 1;

  return (
    <div className="health">
      <p className="inspector-kind">graph health</p>
      <h2 className="inspector-title">Structure</h2>

      <div className="health-grid">
        <Metric label="Nodes" value={
          (stats.counts['nodes:interaction'] ?? 0) +
          (stats.counts['nodes:entity'] ?? 0) +
          (stats.counts['nodes:state'] ?? 0)
        } />
        <Metric label="Components" value={stats.n_components} warn={fragmented} />
        <Metric label="Largest" value={stats.largest_component} />
        <Metric label="Isolated" value={stats.isolated_nodes.length} warn={stats.isolated_nodes.length > 0} />
      </div>

      {fragmented && (
        <p className="health-note health-warn">
          The graph splits into {stats.n_components} components. Fragmentation suggests
          the edge classifier is emitting no_relation too freely.
        </p>
      )}

      <div className="inspector-divider" />

      <p className="field-label">Edges by relation</p>
      {relationRows.length === 0 ? (
        <p className="health-note">
          No classified edges. If the graph was built without an API key, the stub client
          produced nodes but no relations.
        </p>
      ) : (
        <ul className="health-bars">
          {relationRows.map(({ group, label, count }) => {
            const max = Math.max(...relationRows.map((r) => r.count));
            const color = edgeColor(group as never, label);
            return (
              <li key={`${group}:${label}`} className="health-bar-row">
                <span className="health-bar-label" style={{ color }}>{label}</span>
                <span className="health-bar-track">
                  <span className="health-bar-fill" style={{ width: `${(count / max) * 100}%`, background: color }} />
                </span>
                <span className="health-bar-count">{count}</span>
              </li>
            );
          })}
        </ul>
      )}

      {stats.isolated_nodes.length > 0 && (
        <>
          <div className="inspector-divider" />
          <p className="field-label">Isolated nodes ({stats.isolated_nodes.length})</p>
          <div className="tag-row">
            {stats.isolated_nodes.map((id) => (
              <button key={id} className="health-chip" onClick={() => selectNode(id)}>{id}</button>
            ))}
          </div>
          <p className="health-note">
            These turns have no edges at all. Expected for the first turn; worth inspecting
            anywhere else.
          </p>
        </>
      )}

      {stats.dangling_references.length > 0 && (
        <>
          <div className="inspector-divider" />
          <p className="field-label health-warn">Dangling references</p>
          <ul className="health-danglers">
            {stats.dangling_references.map((d, i) => <li key={i}>{d}</li>)}
          </ul>
          <p className="health-note health-warn">
            An edge points at a node that does not exist. Usually a failed extraction call —
            re-running the turn fixes it.
          </p>
        </>
      )}
    </div>
  );
}

function Metric({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className={`metric ${warn ? 'metric-warn' : ''}`}>
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}
