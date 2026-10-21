import { Slot } from "@radix-ui/react-slot";
import type { ButtonHTMLAttributes, JSX, MouseEvent } from "react";
import { cn } from "../cn";
import { assertDialogLabel, textOf } from "../dev";
import { type ForceState, forceAttr } from "../force-state";
import { Icon, type IconName, type IconSize } from "../icons";
import { Ring } from "./pill";

// Button and IconButton (C-00 Shell Kit, Component Sheet E; F-05-T14). Controls are pills: radius
// 999 (`rounded-pill`, DEC-124), which supersedes the 7px squares of TASK-093. One dark primary per
// surface; secondary is white on a 0.5px ring; tonal, ghost, destructive, success and link are
// the quieter ones. Every control presses to scale .985 and brightness .97. A label that opens a
// dialog ends with "…" (`opensDialog`, asserted in development and in tests, plan 04 rule 9).
// Colours are tokens; the hover fills are C-00's (`shell.css` .ac-btn), see tokens/DECISIONS.md,
// "Buttons and pills".

export type ButtonVariant =
  "primary" | "secondary" | "tonal" | "ghost" | "destructive" | "success" | "link";

export const BUTTON_VARIANTS: readonly ButtonVariant[] = [
  "primary",
  "secondary",
  "tonal",
  "ghost",
  "destructive",
  "success",
  "link",
];

/** Heights 23, 28, 30, 32, 34 and 36. The round (29) and icon (28) sizes are `IconButton`. */
export type ButtonSize = "xs" | "sm" | "md" | "lg" | "footer" | "xl";

export const BUTTON_SIZES: readonly ButtonSize[] = ["xs", "sm", "md", "lg", "footer", "xl"];

/** The states a Button can be held in for a specimen. `open` is for menu triggers. */
export type ButtonForceState = Exclude<ForceState, "open">;

// Written out in full so Tailwind sees every class. `data-[force=...]` is a forced state: it draws
// what the pointer would, with no pointer. The pressed fill is the hover fill (the pointer is on
// the control when it is pressed), then scale and brightness.
const VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-espresso font-medium text-on-dark shadow-cta hover:bg-cta-hover data-[force=hover]:bg-cta-hover data-[force=pressed]:bg-cta-hover disabled:bg-nested disabled:text-ink-4 disabled:shadow-none",
  secondary:
    "bg-card text-ink shadow-e1 hover:bg-nested data-[force=hover]:bg-nested data-[force=pressed]:bg-nested disabled:bg-nested disabled:text-ink-4 disabled:shadow-none",
  tonal:
    "bg-chip text-ink hover:bg-tonal-hover data-[force=hover]:bg-tonal-hover data-[force=pressed]:bg-tonal-hover disabled:bg-nested disabled:text-ink-4",
  ghost:
    "text-ink-2 hover:bg-nav-fill data-[force=hover]:bg-nav-fill data-[force=pressed]:bg-nav-fill disabled:text-ink-4",
  destructive:
    "bg-card font-medium text-red-ink shadow-e1 hover:bg-red-tint data-[force=hover]:bg-red-tint data-[force=pressed]:bg-red-tint disabled:bg-nested disabled:text-ink-4 disabled:shadow-none",
  success:
    "bg-green font-medium text-on-dark shadow-cta hover:bg-green-ink data-[force=hover]:bg-green-ink data-[force=pressed]:bg-green-ink disabled:bg-nested disabled:text-ink-4 disabled:shadow-none",
  link: "text-ink-2 hover:text-ink data-[force=hover]:text-ink data-[force=pressed]:text-ink disabled:text-ink-4",
};

// The turning ring of a loading button: ink on a faint track on a light fill, the fill's own ink on
// a 25% track on a dark one (the sheet's `ac-spin`).
const SPINNER: Record<ButtonVariant, { ring: string; track: string }> = {
  primary: { ring: "", track: "stroke-on-dark/25" },
  secondary: { ring: "text-ink", track: "stroke-rule" },
  tonal: { ring: "text-ink", track: "stroke-rule" },
  ghost: { ring: "text-ink", track: "stroke-rule" },
  destructive: { ring: "", track: "stroke-red-ink/20" },
  success: { ring: "", track: "stroke-on-dark/25" },
  link: { ring: "text-ink", track: "stroke-rule" },
};

interface SizeSpec {
  /** Height. */
  h: string;
  /** The type role: 11.5, 12.5, 13 and 13.5. */
  text: string;
  /** Gap and padding with only a label, with a leading icon, and with the leading spinner. */
  plain: string;
  lead: string;
  spin: string;
  /** The icon and spinner box, a registry size. */
  icon: IconSize;
}

// Heights and padding from the sheet (30: 0 13, icon 0 13 0 11, spinner 0 13 0 10 with gap 7; 28:
// 0 12 0 10); the other sizes keep the same steps. Padding is in px: the root font size is 14.
const SIZE: Record<ButtonSize, SizeSpec> = {
  xs: {
    h: "h-[23px]",
    text: "text-meta",
    plain: "gap-[5px] px-[9px]",
    lead: "gap-[5px] pr-[9px] pl-[8px]",
    spin: "gap-[6px] pr-[9px] pl-[8px]",
    icon: 12,
  },
  sm: {
    h: "h-[28px]",
    text: "text-btn-sm",
    plain: "gap-[6px] px-[12px]",
    lead: "gap-[6px] pr-[12px] pl-[10px]",
    spin: "gap-[7px] pr-[12px] pl-[10px]",
    icon: 12,
  },
  md: {
    h: "h-[30px]",
    text: "text-body",
    plain: "gap-[6px] px-[13px]",
    lead: "gap-[6px] pr-[13px] pl-[11px]",
    spin: "gap-[7px] pr-[13px] pl-[10px]",
    icon: 13,
  },
  lg: {
    h: "h-[32px]",
    text: "text-body",
    plain: "gap-[6px] px-[14px]",
    lead: "gap-[6px] pr-[14px] pl-[12px]",
    spin: "gap-[7px] pr-[14px] pl-[11px]",
    icon: 13,
  },
  footer: {
    h: "h-[34px]",
    text: "text-btn",
    plain: "gap-[7px] px-[15px]",
    lead: "gap-[7px] pr-[15px] pl-[13px]",
    spin: "gap-[7px] pr-[15px] pl-[12px]",
    icon: 14,
  },
  xl: {
    h: "h-[36px]",
    text: "text-btn",
    plain: "gap-[7px] px-[16px]",
    lead: "gap-[7px] pr-[16px] pl-[14px]",
    spin: "gap-[7px] pr-[16px] pl-[13px]",
    icon: 14,
  },
};

const BASE =
  "relative inline-flex shrink-0 items-center justify-center rounded-pill font-normal whitespace-nowrap select-none press active:pressed data-[force=pressed]:pressed disabled:pointer-events-none [&_svg]:shrink-0";

// A control under 24px keeps a 24px hit area: a pseudo-element two px taller than the 23px xs
// button, and six px taller than a link's text line.
const HIT_XS = "before:absolute before:inset-x-0 before:-inset-y-px";
const HIT_LINK = "before:absolute before:inset-x-0 before:-inset-y-[3px]";

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "color"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** A registry icon before the label. */
  icon?: IconName;
  /** A registry icon after the label (the link's arrow). */
  iconAfter?: IconName;
  /** Work in flight: the icon gives way to a turning ring and the click does nothing. Say what is
   * happening in the label ("Approving"). */
  loading?: boolean;
  /** The label opens a dialog, so it ends with "…" (U+2026). Asserted in development. */
  opensDialog?: boolean;
  /** Hold the button in a state for a specimen: hover, focus, pressed or loading. */
  forceState?: ButtonForceState;
  /** Render the child (a link, say) with the button's classes instead of a `<button>`. */
  asChild?: boolean;
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  icon,
  iconAfter,
  loading = false,
  opensDialog = false,
  forceState,
  asChild = false,
  type = "button",
  onClick,
  children,
  ...props
}: ButtonProps): JSX.Element {
  const isLoading = loading || forceState === "loading";
  const spec = SIZE[size];
  const isLink = variant === "link";
  if (opensDialog) {
    assertDialogLabel(textOf(children) || (props["aria-label"] ?? ""), "Button");
  }
  const mode = isLoading ? spec.spin : icon === undefined ? spec.plain : spec.lead;
  const classes = cn(
    BASE,
    VARIANT[variant],
    isLink ? cn(spec.text, "gap-[6px]", HIT_LINK) : cn(spec.h, spec.text, mode),
    !isLink && size === "xs" && HIT_XS,
    className,
  );
  const handleClick = (event: MouseEvent<HTMLButtonElement>): void => {
    if (isLoading) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  };
  const common = {
    className: classes,
    "data-variant": variant,
    "data-size": size,
    onClick: handleClick,
    ...(isLoading ? { "aria-busy": true } : {}),
    ...(opensDialog ? { "aria-haspopup": "dialog" as const } : {}),
    ...forceAttr(forceState),
    ...props,
  };
  if (asChild) return <Slot {...common}>{children}</Slot>;
  const lead = isLoading ? (
    <Ring
      size={spec.icon}
      width={1.5}
      track={SPINNER[variant].track}
      className={SPINNER[variant].ring}
    />
  ) : icon === undefined ? null : (
    <Icon name={icon} size={spec.icon} strokeWidth={variant === "success" ? 2 : 1.5} />
  );
  return (
    <button type={type} {...common}>
      {lead}
      {children}
      {iconAfter !== undefined && (
        <Icon name={iconAfter} size={spec.icon} className={isLink ? "text-ink-3" : undefined} />
      )}
    </button>
  );
}

// ---- IconButton --------------------------------------------------------------------------------

/** White 28 on e1 (pane headers), fill 30 on nav-fill (close), dark 29 round (the "+" of a pane). */
export type IconButtonVariant = "white" | "fill" | "dark";

export const ICON_BUTTON_VARIANTS: readonly IconButtonVariant[] = ["white", "fill", "dark"];

interface IconSpec {
  icon: IconSize;
  stroke: number;
}

// The icon sits at 12 in a 28 white control, 14 in the 30 close and the 29 round (stroke 2).
const ICON_VARIANT: Record<IconButtonVariant, string> = {
  white:
    "size-[28px] bg-card text-ink shadow-e1 hover:bg-nested data-[force=hover]:bg-nested data-[force=pressed]:bg-nested aria-pressed:bg-nav-fill disabled:bg-nested disabled:text-ink-4 disabled:shadow-none",
  fill: "size-[30px] bg-nav-fill text-ink hover:bg-sel-bg data-[force=hover]:bg-sel-bg data-[force=pressed]:bg-sel-bg aria-pressed:bg-sel-bg disabled:bg-nested disabled:text-ink-4",
  dark: "size-[29px] bg-espresso text-on-dark shadow-cta hover:bg-cta-hover data-[force=hover]:bg-cta-hover data-[force=pressed]:bg-cta-hover disabled:bg-nested disabled:text-ink-4 disabled:shadow-none",
};

const ICON_SPEC: Record<IconButtonVariant, IconSpec> = {
  white: { icon: 12, stroke: 1.5 },
  fill: { icon: 14, stroke: 1.5 },
  dark: { icon: 14, stroke: 2 },
};

export interface IconButtonProps extends Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "color" | "children" | "aria-label"
> {
  /** The registry icon. */
  icon: IconName;
  /** The accessible name and the hover hint. Required: an icon says nothing to a screen reader. */
  label: string;
  variant?: IconButtonVariant;
  loading?: boolean;
  /** The label opens a dialog, so it ends with "…" (U+2026). Asserted in development. */
  opensDialog?: boolean;
  /** Hold the button in a state for a specimen: hover, focus, pressed or loading. */
  forceState?: ButtonForceState;
}

/** A round icon-only control (C-00): `label` names it, the icon is drawn from the registry. */
export function IconButton({
  icon,
  label,
  variant = "white",
  loading = false,
  opensDialog = false,
  forceState,
  type = "button",
  className,
  onClick,
  ...props
}: IconButtonProps): JSX.Element {
  const isLoading = loading || forceState === "loading";
  if (opensDialog) assertDialogLabel(label, "IconButton");
  const spec = ICON_SPEC[variant];
  const spinner = variant === "dark" ? "stroke-on-dark/25" : "stroke-rule";
  const handleClick = (event: MouseEvent<HTMLButtonElement>): void => {
    if (isLoading) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  };
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      data-variant={variant}
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center rounded-pill press active:pressed data-[force=pressed]:pressed disabled:pointer-events-none",
        ICON_VARIANT[variant],
        className,
      )}
      onClick={handleClick}
      {...(isLoading ? { "aria-busy": true } : {})}
      {...(opensDialog ? { "aria-haspopup": "dialog" as const } : {})}
      {...forceAttr(forceState)}
      {...props}
    >
      {isLoading ? (
        <Ring
          size={spec.icon}
          width={1.5}
          track={spinner}
          className={variant === "dark" ? "" : "text-ink"}
        />
      ) : (
        <Icon name={icon} size={spec.icon} strokeWidth={spec.stroke} />
      )}
    </button>
  );
}
