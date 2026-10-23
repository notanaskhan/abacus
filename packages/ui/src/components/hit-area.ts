// Target size (WCAG 2.2 SC 2.5.8; plan 04 section 3.8): a control drawn under 24px keeps a hit
// area of at least 24px, which a `::before` pseudo-element supplies. It is invisible and sits
// inside the control's positioned box, so it adds no layout and takes the pointer. The control
// carries `relative`. The strings are written in full so Tailwind sees every class.

/** The smallest target the kit allows, in px. */
export const MIN_TARGET = 24;

// One entry per drawn size: the pseudo-element reaches past the box by `inset` on each side.
// A 13px issue ring grows 6 (25), a 15px checkbox 5 (25), a 17px radio 4 (25), a 20px switch 2
// (24), a 22px switch 1 (24), a 16px clear button 4 (24).
export const HIT = {
  /** 13px issue ring. */
  issue: "before:absolute before:-inset-[6px]",
  /** 15px checkbox. */
  checkbox: "before:absolute before:-inset-[5px]",
  /** 17px radio. */
  radio: "before:absolute before:-inset-[4px]",
  /** 17px citation marker (C-07): 25 tall, 24 at its narrowest. */
  marker: "before:absolute before:-inset-[4px]",
  /** 16px clear button in a search field. */
  clear: "before:absolute before:-inset-[4px]",
  /** 22px switch: taller by one px a side. */
  switch22: "before:absolute before:inset-x-0 before:-inset-y-px",
  /** 20px switch: taller by two px a side. */
  switch20: "before:absolute before:inset-x-0 before:-inset-y-[2px]",
} as const;
