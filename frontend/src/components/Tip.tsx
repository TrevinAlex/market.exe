import { cloneElement, isValidElement, useId, useState, type ReactElement, type ReactNode } from 'react';

interface TipProps {
  /** Explanation shown in the pop-up. */
  text: ReactNode;
  children: ReactNode;
  /**
   * Set when the child is already interactive (a <button>, a link). The tooltip
   * is then attached to that element instead of making the wrapper focusable.
   */
  interactive?: boolean;
  /** Which edge the pop-up lines up with. Use 'right' near the right side of the screen. */
  align?: 'left' | 'right';
}

/**
 * Small explanatory pop-up shown on hover and on keyboard focus.
 * Escape dismisses it; moving the pointer onto the pop-up keeps it open.
 */
export function Tip({ text, children, interactive = false, align = 'left' }: TipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);

  const show = () => setOpen(true);
  const hide = () => setOpen(false);

  // For an interactive child, put aria-describedby on the child itself so screen
  // readers announce the explanation when the button receives focus.
  const trigger =
    interactive && isValidElement(children)
      ? cloneElement(children as ReactElement<{ 'aria-describedby'?: string }>, { 'aria-describedby': id })
      : children;

  return (
    <span
      className={['tip-wrap', interactive ? '' : 'tip-term', align === 'right' ? 'tip-right' : '']
        .filter(Boolean)
        .join(' ')}
      tabIndex={interactive ? undefined : 0}
      aria-describedby={interactive ? undefined : id}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      onKeyDown={(e) => {
        if (e.key === 'Escape') hide();
      }}
    >
      {trigger}
      <span role="tooltip" id={id} className="tip" data-open={open || undefined}>
        {text}
      </span>
    </span>
  );
}
