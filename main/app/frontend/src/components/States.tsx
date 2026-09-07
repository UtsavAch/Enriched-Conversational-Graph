import type { ReactNode } from 'react';
import { Button } from './Button';
import './States.css';

/**
 * Loading, empty and error states.
 *
 * Grouped in one file because they are variations on the same layout, and
 * because keeping them together makes it obvious when one is missing. Every
 * async surface in the app should render one of these rather than nothing.
 */

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="state-screen" role="status" aria-live="polite">
      <div className="spinner" />
      {label && <span className="state-text">{label}</span>}
    </div>
  );
}

/** An empty screen is an invitation to act, so it takes an action when there
 *  is one worth offering. */
export function EmptyState({ title, hint, action }: {
  title: string;
  hint?: ReactNode;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="state-screen">
      <p className="state-title">{title}</p>
      {hint && <p className="state-hint">{hint}</p>}
      {action && <Button variant="primary" onClick={action.onClick}>{action.label}</Button>}
    </div>
  );
}

/** Errors say what happened and how to fix it. They do not apologise and they
 *  are never vague — a wall of "Something went wrong" helps nobody debug a
 *  server that is not running. */
export function ErrorState({ title, detail, onRetry }: {
  title: string;
  detail?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="state-screen" role="alert">
      <p className="state-title state-error">{title}</p>
      {detail && <pre className="state-detail">{detail}</pre>}
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
    </div>
  );
}
