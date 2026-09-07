import './Chip.css';

interface Props {
  label: string;
  color: string;
  active: boolean;
  shape?: 'square' | 'dot' | 'diamond';
  onToggle: () => void;
}

/** A filter toggle. Rendered as a real checkbox for keyboard and screen-reader
 *  users, with the visual treatment layered on top. */
export function Chip({ label, color, active, shape = 'square', onToggle }: Props) {
  return (
    <label className={`chip ${active ? '' : 'chip-off'}`}>
      <input
        type="checkbox"
        checked={active}
        onChange={onToggle}
        className="sr-only"
      />
      <span className={`chip-swatch chip-swatch-${shape}`} style={{ background: color }} aria-hidden />
      <span className="chip-label">{label}</span>
    </label>
  );
}
