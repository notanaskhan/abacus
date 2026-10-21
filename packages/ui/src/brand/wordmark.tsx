import clsx from "clsx";
import type { JSX } from "react";

// The Accrued wordmark (Foundations 01 Brand, F-05-T14). There is no logo file: it is Geist 500
// type, "accrued" in lowercase, with a square olive posted dot after the "d". The tracking is the
// brand's: -0.035em on the run, -0.045em on the first "c" (so the two c's close up by a further
// -0.01em) and 0 on the "d". Colours are the espresso and green tokens; the brand has no others.

/** The smallest the brand allows. */
export const WORDMARK_MIN = 12;

export interface WordmarkProps {
  /** Font size in px: 76 hero, 44, 20 sign-in, 12.5 palette, firm menu and portal footer. At least 12. */
  size?: number;
  /** The accessible name. The mark is type, so it is read as the product name. */
  label?: string;
  className?: string;
}

/**
 * The wordmark. It appears on firm sign-in, the command-palette and firm-menu footers, the portal
 * footer ("Secured by" and the mark, off by default) and the tenant console (PLT-01); never in the
 * firm app's chrome, and the client portal shows the firm's own mark instead (FirmMark). Needs
 * Geist loaded; one x-height of clear space on every side is the caller's to leave.
 */
export function Wordmark({ size = 20, label = "Accrued", className }: WordmarkProps): JSX.Element {
  return (
    <span
      role="img"
      aria-label={label}
      data-brand="wordmark"
      className={clsx(
        "inline-block font-sans font-medium leading-none tracking-[-0.035em] whitespace-nowrap text-espresso",
        className,
      )}
      style={{ fontSize: Math.max(size, WORDMARK_MIN) }}
    >
      <span aria-hidden="true">
        a<span className="tracking-[-0.045em]">c</span>crue<span className="tracking-[0]">d</span>
        <span className="ml-[0.06em] inline-block size-[0.18em] rounded-[0.04em] bg-green" />
      </span>
    </span>
  );
}
