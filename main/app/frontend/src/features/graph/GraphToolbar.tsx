import { useUiStore } from '@/store/uiStore';
import { Chip } from '@/components/Chip';
import { GROUP_COLOR, NODE_COLOR, EDGE_GROUP_LABEL } from '@/lib/graphStyles';
import type { EdgeGroup, NodeKind } from '@/types/api';
import './GraphToolbar.css';

const NODE_CHIPS: { key: NodeKind; label: string; color: string; shape: 'dot' | 'diamond' | 'square' }[] = [
  { key: 'interaction', label: 'Interaction', color: NODE_COLOR.interaction, shape: 'dot' },
  { key: 'entity', label: 'Entity', color: NODE_COLOR.entity, shape: 'diamond' },
  { key: 'state', label: 'State', color: NODE_COLOR.decision, shape: 'square' },
];

const EDGE_GROUPS: EdgeGroup[] = ['hierarchical', 'pragmatic', 'state_link', 'citation', 'mention'];

export function GraphToolbar() {
  const viewMode = useUiStore((s) => s.viewMode);
  const setViewMode = useUiStore((s) => s.setViewMode);
  const nodeFilters = useUiStore((s) => s.nodeFilters);
  const edgeFilters = useUiStore((s) => s.edgeFilters);
  const toggleNodeFilter = useUiStore((s) => s.toggleNodeFilter);
  const toggleEdgeFilter = useUiStore((s) => s.toggleEdgeFilter);

  return (
    <div className="toolbar">
      <div className="toolbar-group">
        <span className="toolbar-label">Layout</span>
        <div className="segmented" role="group" aria-label="Layout mode">
          <button
            className={viewMode === 'graph' ? 'active' : ''}
            onClick={() => setViewMode('graph')}
            aria-pressed={viewMode === 'graph'}
          >Force</button>
          <button
            className={viewMode === 'timeline' ? 'active' : ''}
            onClick={() => setViewMode('timeline')}
            aria-pressed={viewMode === 'timeline'}
          >Timeline</button>
        </div>
      </div>

      <div className="toolbar-group">
        <span className="toolbar-label">Nodes</span>
        {NODE_CHIPS.map((c) => (
          <Chip
            key={c.key} label={c.label} color={c.color} shape={c.shape}
            active={nodeFilters[c.key]} onToggle={() => toggleNodeFilter(c.key)}
          />
        ))}
      </div>

      <div className="toolbar-group">
        <span className="toolbar-label">Edges</span>
        {EDGE_GROUPS.map((g) => (
          <Chip
            key={g} label={EDGE_GROUP_LABEL[g]} color={GROUP_COLOR[g]}
            active={edgeFilters[g]} onToggle={() => toggleEdgeFilter(g)}
          />
        ))}
      </div>
    </div>
  );
}
