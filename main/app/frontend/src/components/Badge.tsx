import type { CSSProperties, ReactNode } from 'react';
import './Badge.css';

interface Props {
  children: ReactNode;
  bg?: string;
  fg?: string;
  mono?: boolean;
  title?: string;
}

/** A small status pill. Colour is passed in rather than derived here, so the
 *  schema-to-colour mapping stays in `lib/graphStyles.ts`. */
export function Badge({ children, bg = 'var(--neutral-soft)', fg = 'var(--ink-soft)', mono = true, title }: Props) {
  const style: CSSProperties = { background: bg, color: fg, fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)' };
  return <span className="badge" style={style} title={title}>{children}</span>;
}
