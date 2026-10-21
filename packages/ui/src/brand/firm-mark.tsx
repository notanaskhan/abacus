import clsx from "clsx";
import type { JSX } from "react";
import { firmInitials } from "./initials";

// The firm's own mark (C-00 PortalToolbar "firm logo slot", T15 auth card, ADM-10; F-05-T14). The
// client portal is white-labelled: it shows the firm's logo and name and never the Accrued mark
// (DEC-01, ADR-133). The firm app's chrome shows no mark at all, so FirmMark belongs to the
// portal, the auth card and the branding screen, not to the firm toolbar.
//
// Three forms: the tenant's uploaded logo (`src`), a tile with the firm's initials, and the demo
// firm's wave mark the kit draws (`mark="wave"`). Colours are tokens; a firm cannot change them.

export const FIRM_MARK_SIZES = [20, 34] as const;
export type FirmMarkSize = (typeof FIRM_MARK_SIZES)[number];

export interface FirmMarkProps {
  /** The firm's name. It is the accessible name, and its first two words give the initials. */
  name: string;
  /** 20 in the portal toolbar and the branding preview, 34 on the auth card (T15). */
  size?: FirmMarkSize;
  /** The tenant's uploaded logo (ADM-10). Without it the mark is drawn from the name. */
  src?: string;
  /** `initials` (default) or the demo firm's `wave` mark; ignored when `src` is given. */
  mark?: "initials" | "wave";
  className?: string;
}

const BOX: Record<FirmMarkSize, string> = { 20: "size-[20px]", 34: "size-[34px]" };

/** The tile's initials are 8.5px at 20 and scale with the box. */
const INITIALS_RATIO = 8.5 / 20;

function Wave({ size, name }: { size: FirmMarkSize; name: string }): JSX.Element {
  return (
    <svg
      role="img"
      aria-label={name}
      data-brand="firm-mark"
      data-mark="wave"
      width={size}
      height={size}
      viewBox="0 0 20 20"
      className="block flex-none"
    >
      <rect
        x=".25"
        y=".25"
        width="19.5"
        height="19.5"
        rx="5"
        className="fill-card stroke-stroke"
        strokeWidth=".5"
      />
      <path
        d="M3.6 10.9c1.6-2.7 3.4-2.7 5 0s3.4 2.7 5 0 2.1-1.9 2.8-1.4"
        fill="none"
        className="stroke-espresso"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M3.6 9.1c1.6 2.7 3.4 2.7 5 0s3.4-2.7 5 0 2.1 1.9 2.8 1.4"
        fill="none"
        className="stroke-espresso"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** The firm's mark: radius 5, a hairline ring, 20px (34px on the auth card). */
export function FirmMark({
  name,
  size = 20,
  src,
  mark = "initials",
  className,
}: FirmMarkProps): JSX.Element {
  if (src === undefined && mark === "wave") return <Wave size={size} name={name} />;
  if (src !== undefined) {
    return (
      <img
        src={src}
        alt={name}
        data-brand="firm-mark"
        data-mark="logo"
        className={clsx(
          "block flex-none rounded-prop bg-card object-contain inset-shadow-hair",
          BOX[size],
          className,
        )}
      />
    );
  }
  return (
    <span
      role="img"
      aria-label={name}
      data-brand="firm-mark"
      data-mark="initials"
      className={clsx(
        "inline-flex flex-none items-center justify-center rounded-prop bg-chip font-medium tracking-[0.02em] text-ink-2 inset-shadow-hair",
        BOX[size],
        className,
      )}
      style={{ fontSize: size * INITIALS_RATIO }}
    >
      <span aria-hidden="true">{firmInitials(name)}</span>
    </span>
  );
}
