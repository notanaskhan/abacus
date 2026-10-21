import type { JSX, SVGAttributes } from "react";
import { cn } from "../cn";
import { ICON_STROKE, type IconSize } from "./icon";

// Custom glyphs (F-05-T13, SPEC-048 B3): the marks the handoff draws itself rather than takes from
// lucide. Each is an SVG on its own viewBox with every length, stroke included, in viewBox units,
// so it scales with its box like a lucide icon. No brand colours: strokes and fills are
// `currentColor` or a design token, and a vendor is never drawn in its own colours.

type SvgProps = Omit<
  SVGAttributes<SVGSVGElement>,
  "children" | "width" | "height" | "viewBox" | "fill" | "stroke" | "strokeWidth"
>;

interface GlyphProps extends SvgProps {
  /** Accessible name, only when nothing beside the glyph says it. Otherwise hidden. */
  label?: string;
}

function a11y(label: string | undefined) {
  return label === undefined
    ? ({ "aria-hidden": true } as const)
    : ({ role: "img", "aria-label": label } as const);
}

/**
 * The Accrued Agent's mark: the atom (C-26, C-33, C-34), never Sparkles. Three orbits and a
 * nucleus on lucide's 24-unit grid, stroked at 1.5.
 */
export function AtomMark({
  size = 12,
  label,
  className,
  ...rest
}: GlyphProps & { size?: IconSize }): JSX.Element {
  return (
    <svg
      data-glyph="atom-mark"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={ICON_STROKE}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      className={cn("block flex-none", className)}
      {...a11y(label)}
      {...rest}
    >
      <circle cx="12" cy="12" r="1" />
      <ellipse cx="12" cy="12" rx="10" ry="4" />
      <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)" />
      <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)" />
    </svg>
  );
}

/**
 * The in-progress status disc (`ac-disc st="half"`): a ring with the left half filled. Ring and fill
 * are the current colour, so the caller sets ink with `text-ink`.
 */
export function HalfDisc({
  size = 15,
  label,
  className,
  ...rest
}: GlyphProps & { size?: IconSize }): JSX.Element {
  return (
    <svg
      data-glyph="half-disc"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={ICON_STROKE}
      focusable="false"
      className={cn("block flex-none", className)}
      {...a11y(label)}
      {...rest}
    >
      <circle cx="12" cy="12" r="11.25" />
      <path d="M12 0.75a11.25 11.25 0 0 0 0 22.5Z" fill="currentColor" stroke="none" />
    </svg>
  );
}

/**
 * The Accrued Agent's avatar (brand spec 01): the espresso tile with the lowercase "a" and the
 * green posted dot. 16 is the smallest it is drawn; the radius is 28% of the side. Drawn on a
 * 100-unit viewBox so the glyph scales with the tile; the "a" is Geist 500 at 0.62 of the side.
 */
export function AgentMonogram({
  size = 16,
  label,
  className,
  ...rest
}: GlyphProps & { size?: number }): JSX.Element {
  return (
    <svg
      data-glyph="agent-monogram"
      viewBox="0 0 100 100"
      width={size}
      height={size}
      focusable="false"
      className={cn("block flex-none", className)}
      {...a11y(label)}
      {...rest}
    >
      <rect width="100" height="100" rx="28" className="fill-espresso" />
      <text
        x="43"
        y="61"
        textAnchor="middle"
        fontSize="62"
        letterSpacing="-2.17"
        className="fill-on-dark font-sans font-medium"
      >
        a
      </text>
      <rect x="62.5" y="49.8" width="11.2" height="11.2" rx="2.5" className="fill-green" />
    </svg>
  );
}

/** The fills a vendor tile may take: the C-14 category colours, never the vendor's own. */
export const VENDOR_TONES = ["green", "espresso", "clay", "amber", "red"] as const;
export type VendorTone = (typeof VENDOR_TONES)[number];

const TONE_FILL: Record<VendorTone, string> = {
  green: "fill-green",
  espresso: "fill-espresso",
  clay: "fill-clay",
  amber: "fill-amber",
  red: "fill-red",
};

/**
 * Up to two capitals for a vendor tile: the initials of its first two words, or the first letter
 * of a single word ("Xero" is "X", "QuickBooks Online" is "QO"). Empty text gives "?".
 */
export function vendorMonogram(name: string): string {
  const words = name
    .trim()
    .split(/[\s\-_/&.]+/u)
    .filter(Boolean);
  const letters = words.slice(0, 2).map((w) => w.slice(0, 1).toUpperCase());
  return letters.join("") || "?";
}

/**
 * An integration or vendor tile (C-14 IntegrationTile, WB-10): a rounded square in a category
 * colour with the vendor's initials. No vendor logos and no brand colours, ever.
 */
export function VendorTile({
  name,
  tone = "espresso",
  size = 32,
  label,
  className,
  ...rest
}: GlyphProps & { name: string; tone?: VendorTone; size?: number }): JSX.Element {
  const mono = vendorMonogram(name);
  return (
    <svg
      data-glyph="vendor-tile"
      data-monogram={mono}
      viewBox="0 0 32 32"
      width={size}
      height={size}
      focusable="false"
      className={cn("block flex-none", className)}
      {...a11y(label)}
      {...rest}
    >
      <rect width="32" height="32" rx="8" className={TONE_FILL[tone]} />
      <text
        x="16"
        y="21"
        textAnchor="middle"
        fontSize="14"
        letterSpacing="-0.3"
        className="fill-on-dark font-sans font-medium"
      >
        {mono}
      </text>
    </svg>
  );
}
