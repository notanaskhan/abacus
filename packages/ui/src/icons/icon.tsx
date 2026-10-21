import type { JSX, SVGAttributes } from "react";
import { cn } from "../cn";
import type { IconName } from "./names";
import { ICONS } from "./registry";

// The one icon component (F-05-T13, SPEC-048 B3). The handoff draws lucide on a 24-unit viewBox at
// 1.5 stroke, round caps and joins, sized by the box (`<lc-i n s w f>`): the stroke scales with the
// icon, so it stays in viewBox units. Lucide's `absoluteStrokeWidth` and `nonScalingStroke` stay
// off (their defaults); icons.test.ts fails on a pixel stroke.

/** Sizes the handoff draws icons at: 12 inside 28px controls, 14 default, 17 inside 34px tiles. */
export const ICON_SIZES = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22] as const;
export type IconSize = (typeof ICON_SIZES)[number];

/** The default stroke, in viewBox units (`w="1.5"` in the handoff). */
export const ICON_STROKE = 1.5;

export interface IconProps extends Omit<
  SVGAttributes<SVGSVGElement>,
  "children" | "width" | "height" | "viewBox" | "fill" | "stroke" | "strokeWidth" | "name"
> {
  name: IconName;
  /** Box side in px; the glyph and its stroke scale with it. Default 14. */
  size?: IconSize;
  /**
   * Stroke in viewBox units. 1.5 by default; the handoff uses 1.9 for disc checks and 2.2 to 2.8
   * for pill checks.
   */
  strokeWidth?: number;
  /** Fill with the current colour (the Support bubble, `f` in the handoff). */
  filled?: boolean;
  /**
   * Set only when the icon carries meaning that nothing beside it says. It becomes the accessible
   * name; without it the icon is hidden from assistive technology.
   */
  label?: string;
}

/** A lucide glyph from the registry, coloured by CSS `color`. */
export function Icon({
  name,
  size = 14,
  strokeWidth = ICON_STROKE,
  filled = false,
  label,
  className,
  ...rest
}: IconProps): JSX.Element {
  const Glyph = ICONS[name];
  const a11y =
    label === undefined
      ? ({ "aria-hidden": true } as const)
      : ({ role: "img", "aria-label": label } as const);
  return (
    <Glyph
      data-icon={name}
      size={size}
      strokeWidth={strokeWidth}
      fill={filled ? "currentColor" : "none"}
      focusable="false"
      className={cn("block flex-none", className)}
      {...a11y}
      {...rest}
    />
  );
}
