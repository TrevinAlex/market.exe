import { cloneElement, isValidElement, useId, useState, type ReactElement, type ReactNode } from 'react';

interface TipProps {
  text: ReactNode;
  children: ReactNode;
  interactive?: boolean;
  align?: 'left' | 'right';
}

export function Tip({ text, children, interactive = false, align = 'left' }: TipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);

  const show = () => setOpen(true);
  const hide = () => setOpen(false);

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
