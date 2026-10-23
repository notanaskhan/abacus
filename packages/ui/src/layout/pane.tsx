import {
  type CSSProperties,
  type JSX,
  type ReactNode,
  type RefObject,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { cn } from "../cn";
import { Button, type ButtonProps, IconButton } from "../components/button";
import { PRESS } from "../components/control-classes";
import { Icon, type IconName } from "../icons";

// Pane and PaneHeader (C-00 Shell Kit spec 06; F-05-T18). A pane is white, radius 12, e2, no
// border, and panes are 10px apart (the body row's gap), never touching. Its header is 46 high
// with the title at 14.5 / 500, centred or left; its body scrolls (the page never does); a footer
// is optional. Plan 04 4.5 rule 5: chrome takes slots, so the header's `left` and `right` and the
// pane's `footer` are nodes, and `PaneAction` and `FooterAction` draw the kit's action kinds.

// ---- Actions ----------------------------------------------------------------------------------

export type PaneActionKind = "icon" | "round" | "pill" | "picker" | "meta";

export interface PaneActionProps {
  /** `icon` 28 white, `round` 29 espresso, `pill` 28 with an optional icon, `picker` with a
   * chevron, `meta` plain text. Default `pill`; name `icon` and `round` actions explicitly. */
  kind?: PaneActionKind;
  icon?: IconName;
  /** The text of a pill, picker or meta, and the accessible name of an icon or round action. */
  label: string;
  onClick?: () => void;
  /** The label opens a dialog, so it ends with "…". */
  opensDialog?: boolean;
  disabled?: boolean;
}

/** One action in a pane header's `left` or `right`. */
export function PaneAction({
  kind,
  icon,
  label,
  onClick,
  opensDialog = false,
  disabled = false,
}: PaneActionProps): JSX.Element {
  const resolved: PaneActionKind = kind ?? "pill";
  switch (resolved) {
    case "icon":
    case "round":
      return (
        <IconButton
          icon={icon ?? "ellipsis"}
          label={label}
          variant={resolved === "icon" ? "white" : "dark"}
          opensDialog={opensDialog}
          disabled={disabled}
          {...(onClick === undefined ? {} : { onClick })}
        />
      );
    case "picker":
      return (
        <button
          type="button"
          disabled={disabled}
          onClick={onClick}
          className={cn(
            "inline-flex h-[28px] flex-none items-center gap-[5px] rounded-pill bg-card pr-[9px] pl-[11px] text-body text-ink shadow-e1 hover:bg-nested disabled:text-ink-4",
            PRESS,
          )}
        >
          {label}
          <Icon name="chevron-down" size={12} className="text-ink-3" />
        </button>
      );
    case "meta":
      return <span className="px-[4px] text-body whitespace-nowrap text-ink-2">{label}</span>;
    case "pill":
      return (
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled}
          opensDialog={opensDialog}
          {...(icon === undefined ? {} : { icon })}
          {...(onClick === undefined ? {} : { onClick })}
        >
          {label}
        </Button>
      );
  }
}

export type FooterActionKind = "primary" | "secondary" | "ghost" | "destructive";

export interface FooterActionProps extends Pick<ButtonProps, "onClick" | "disabled" | "loading"> {
  kind?: FooterActionKind;
  opensDialog?: boolean;
  children: ReactNode;
}

/** A footer button (30 high). The canonical order is Cancel (ghost), a spacer, Save draft
 * (secondary), Send (primary). */
export function FooterAction({
  kind = "secondary",
  opensDialog = false,
  children,
  ...props
}: FooterActionProps): JSX.Element {
  return (
    <Button variant={kind} size="md" opensDialog={opensDialog} {...props}>
      {children}
    </Button>
  );
}

/** Pushes the actions after it to the right of the footer. */
export function FooterSpacer(): JSX.Element {
  return <span aria-hidden="true" className="flex-1" />;
}

// ---- PaneHeader -------------------------------------------------------------------------------

// A centred title may not run under an action: its width is the pane less twice the wider
// cluster plus 16.
const SIDE_PAD = 16;

function useSide(
  left: RefObject<HTMLElement | null>,
  right: RefObject<HTMLElement | null>,
  active: boolean,
): number {
  const [side, setSide] = useState(SIDE_PAD);
  useLayoutEffect(() => {
    if (!active) return undefined;
    const l = left.current;
    const r = right.current;
    const read = (): void => {
      const widest = Math.max(l?.offsetWidth ?? 0, r?.offsetWidth ?? 0);
      setSide((prev) => (prev === widest + SIDE_PAD ? prev : widest + SIDE_PAD));
    };
    read();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(read);
    if (l !== null) observer?.observe(l);
    if (r !== null) observer?.observe(r);
    return () => {
      observer?.disconnect();
    };
  }, [left, right, active]);
  return side;
}

export interface PaneHeaderProps {
  title?: string;
  /** Centred on the pane (default), or left after the left actions. */
  titleAlign?: "center" | "left";
  left?: ReactNode;
  right?: ReactNode;
  /** The title's element id, so a pane can name itself by it. */
  titleId?: string;
  className?: string;
}

/** The 46px header: a centred or left title, `left` and `right` action clusters, a hairline under. */
export function PaneHeader({
  title,
  titleAlign = "center",
  left,
  right,
  titleId,
  className,
}: PaneHeaderProps): JSX.Element {
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const centred = titleAlign === "center";
  const side = useSide(leftRef, rightRef, centred);
  const titleStyle: CSSProperties | undefined = centred
    ? { maxWidth: `calc(100% - ${String(side * 2)}px)` }
    : undefined;
  return (
    <div
      data-shell="pane-header"
      className={cn(
        "relative flex h-(--pane-hd-h) flex-none items-center gap-[6px] bg-card px-(--gutter-pane) hairline-b",
        className,
      )}
    >
      {left !== undefined && (
        <div ref={leftRef} className="flex flex-none items-center gap-[6px]">
          {left}
        </div>
      )}
      {title !== undefined && centred && (
        <h2
          id={titleId}
          data-title="center"
          style={titleStyle}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 truncate text-pane font-medium tracking-[-0.012em] whitespace-nowrap"
        >
          {title}
        </h2>
      )}
      {title !== undefined && !centred && (
        <h2
          id={titleId}
          data-title="left"
          className="min-w-0 flex-1 truncate pl-[6px] text-pane font-medium tracking-[-0.012em] whitespace-nowrap"
        >
          {title}
        </h2>
      )}
      {centred && <span aria-hidden="true" className="flex-1" />}
      {right !== undefined && (
        <div ref={rightRef} className="flex flex-none items-center gap-[6px]">
          {right}
        </div>
      )}
    </div>
  );
}

// ---- Pane -------------------------------------------------------------------------------------

export interface PaneProps extends Omit<PaneHeaderProps, "titleId" | "className"> {
  /** A fixed width in px (330, 336, 358, 392, 470, 536 ...) or `flex` (1 1 0, the default). */
  width?: number | "flex";
  /** `false` hides the header. */
  header?: boolean;
  /** The body sits on the shell colour (documents on a well). */
  well?: boolean;
  /** A footer row: padding 10, gap 8, a hairline above. */
  footer?: ReactNode;
  /** The body scrolls and may hold no control (a feed, a read-only form): it becomes a focusable
   * region of this name so the keyboard can scroll it (axe scrollable-region-focusable). */
  scrollLabel?: string;
  className?: string;
  children?: ReactNode;
}

export function Pane({
  width = "flex",
  header = true,
  well = false,
  title,
  titleAlign,
  left,
  right,
  footer,
  scrollLabel,
  className,
  children,
}: PaneProps): JSX.Element {
  const id = useId();
  const named = header && title !== undefined;
  return (
    <section
      data-shell="pane"
      aria-labelledby={named ? id : undefined}
      style={width === "flex" ? undefined : { width }}
      className={cn(
        "pane flex min-w-0 flex-col overflow-hidden",
        width === "flex" ? "flex-[1_1_0%]" : "flex-none",
        className,
      )}
    >
      {header && (
        <PaneHeader
          {...(title === undefined ? {} : { title })}
          {...(titleAlign === undefined ? {} : { titleAlign })}
          {...(left === undefined ? {} : { left })}
          {...(right === undefined ? {} : { right })}
          titleId={id}
        />
      )}
      <div
        {...(scrollLabel === undefined
          ? {}
          : { role: "region", "aria-label": scrollLabel, tabIndex: 0 })}
        className={cn("min-h-0 flex-1 overflow-auto", well && "bg-shell")}
      >
        {children}
      </div>
      {footer !== undefined && (
        <div className="flex flex-none items-center gap-[8px] p-[10px] hairline-t">{footer}</div>
      )}
    </section>
  );
}
