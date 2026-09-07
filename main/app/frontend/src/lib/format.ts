/** Small presentation helpers. No business logic. */

export function truncate(s: string | undefined, n: number): string {
  if (!s) return '';
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/** `factual_question` → `factual question`. Enum values are snake_case; humans
 *  are not. */
export function humanize(value: string): string {
  return value.replace(/_/g, ' ');
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/** A node's display name, whatever kind it is. Used in relation lists and
 *  tooltips, where the caller should not have to branch on kind. */
export function displayName(node: {
  kind: string;
  data: Record<string, unknown>;
}): string {
  const d = node.data;
  if (node.kind === 'interaction') {
    return (d.summary as string) || (d.reference as string) || (d.question as string) || '';
  }
  if (node.kind === 'entity') return (d.name as string) ?? '';
  return (d.label as string) ?? '';
}
