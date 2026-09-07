import { edgeColor, EDGE_GROUP_LABEL } from '@/lib/graphStyles';
import { truncate } from '@/lib/format';
import type { RelationRef } from '@/types/api';

/**
 * Every edge touching the selected node, grouped by kind.
 *
 * Grouped rather than flat because the groups mean different things: a
 * pragmatic relation is a claim the classifier made about discourse, while a
 * mention is a mechanical by-product of entity extraction. Presenting them in
 * one undifferentiated list implies they carry equal weight, which they do not.
 */
export function RelationList({ relations, onJump }: {
  relations: RelationRef[];
  onJump: (id: string) => void;
}) {
  if (relations.length === 0) {
    return (
      <>
        <p className="field-label">Connected edges</p>
        <p className="field-note" style={{ marginTop: 6 }}>
          This node is isolated. During validation that is worth noting — it may mean the
          edge classifier emitted no_relation where a relation exists.
        </p>
      </>
    );
  }

  // Ordered by how much the relation tells you, most informative first.
  const order = ['pragmatic', 'hierarchical', 'state_link', 'citation', 'mention'] as const;
  const grouped = order
    .map((group) => ({ group, items: relations.filter((r) => r.group === group) }))
    .filter((g) => g.items.length > 0);

  return (
    <>
      <p className="field-label">Connected edges ({relations.length})</p>

      {grouped.map(({ group, items }) => (
        <section key={group} className="rel-group">
          <p className="rel-group-label">{EDGE_GROUP_LABEL[group]}</p>
          <ul className="rel-list">
            {items.map((r, i) => {
              const color = edgeColor(r.group, r.label);
              return (
                <li key={`${r.other}-${r.label}-${i}`}>
                  <button className="rel-item" onClick={() => onJump(r.other)}>
                    <span className="rel-arrow">{r.direction === 'out' ? '→' : '←'}</span>
                    <span className="rel-tag" style={{ background: `${color}22`, color }}>
                      {r.label}
                    </span>
                    <span className="rel-target">{r.other}</span>
                    <span className="rel-name">{truncate(r.other_name, 30)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </>
  );
}
