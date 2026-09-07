import { useEffect, useRef, type ReactNode } from 'react';
import './Dialog.css';

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

/**
 * A modal built on the native `<dialog>` element, which gives focus trapping,
 * Escape-to-close and inertness of the background for free — all things that
 * are easy to get subtly wrong by hand.
 */
export function Dialog({ open, title, onClose, children, footer }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="dialog"
      onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}
    >
      <h2 className="dialog-title">{title}</h2>
      <div className="dialog-body">{children}</div>
      {footer && <div className="dialog-footer">{footer}</div>}
    </dialog>
  );
}
