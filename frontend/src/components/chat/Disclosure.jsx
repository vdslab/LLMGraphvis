import { useState, useEffect } from 'react';
import { ChevronRight } from 'lucide-react';

/**
 * A labelled block the user can fold away.
 *
 * Everything secondary in a message — reasoning, the pipeline log, the action
 * log, the upload overview — uses this, so they read as one family and the
 * panel stays scannable. `forceOpen` holds it open while its content is still
 * streaming, then releases control back to the user.
 */
const Disclosure = ({
  icon,
  label,
  meta,
  tone = 'default',
  defaultOpen = false,
  forceOpen = false,
  children,
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen || forceOpen);
  const [userDecided, setUserDecided] = useState(false);

  // Follow forceOpen in both directions — reasoning unfolds while it streams
  // and folds itself away once the turn is over, leaving the panel as it looks
  // on reload. One click opts out of that for good.
  useEffect(() => {
    if (!userDecided) setIsOpen(defaultOpen || forceOpen);
  }, [forceOpen, defaultOpen, userDecided]);

  const toggle = () => {
    setUserDecided(true);
    setIsOpen((open) => !open);
  };

  return (
    <div className={`disclosure disclosure--${tone} ${isOpen ? 'is-open' : ''}`}>
      <button
        type="button"
        className="disclosure__summary"
        onClick={toggle}
        aria-expanded={isOpen}
      >
        <ChevronRight size={14} className="disclosure__chevron" aria-hidden />
        {icon && <span className="disclosure__icon">{icon}</span>}
        <span className="disclosure__label">{label}</span>
        {meta && <span className="disclosure__meta">{meta}</span>}
      </button>
      {isOpen && <div className="disclosure__body">{children}</div>}
    </div>
  );
};

export default Disclosure;
