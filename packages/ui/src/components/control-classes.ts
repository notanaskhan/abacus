// Class strings the form and tab controls share (F-05-T15), written in full so Tailwind sees them.

/** Colour changes over 180ms and a press scales to .985 at brightness .97 over 220ms (utilities.css
 * `press` and `pressed`); `data-[force=pressed]` draws the press with no pointer. */
export const PRESS = "press active:pressed data-[force=pressed]:pressed";

/** A control that is a pill on the white card ground: e1, then nav-fill on hover. */
export const PILL_WHITE = "bg-card shadow-e1 hover:bg-nav-fill data-[force=hover]:bg-nav-fill";
