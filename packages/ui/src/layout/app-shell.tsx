import { type JSX, type ReactNode, useEffect } from "react";
import { cn } from "../cn";
import { PortalFooter, PortalToolbar, type PortalToolbarProps } from "./portal-toolbar";
import { Toolbar, type ToolbarProps } from "./toolbar";

// AppShell (C-00 Shell Kit spec 01; F-05-T18): the frame every screen is built in. Top to bottom:
// the toolbar (46), an optional record header (42, 59 or 42 + 50), an optional tabsbar (50, 44
// or 60), then the body row of panes (gap 10, padding 10 12 12, `flex: 1`, `min-height: 0`), and
// on the portal the "Secured by" footer when the firm turns it on. There is never a left sidebar,
// a heading above the panes, a coloured top bar or an underline nav. The page never scrolls; the
// panes' bodies do.
//
// The shell draws what it is given. The nav items, the active one and every handler are props
// (the app owns the list, apps/web/src/shell/nav.ts; this package imports nothing from the app).
// The command palette is a slot drawn over the shell (`overlay`); Go... and Ctrl or Cmd K call the
// toolbar's `onGo`, in the firm shell only and never in the portal.

interface ShellCommon {
  /** Presentation only (the gallery's `?frame=1`): a 1400-wide window, radius 16, on the
   * presentation ground. Not product behaviour: the product fills the viewport. */
  frame?: boolean;
  /** Framed without the ground and padding (a canvas already provides them). */
  embedded?: boolean;
  /** A fixed window height in px, framed only. */
  height?: number;
  /** The RecordHeader, if the screen has one. */
  record?: ReactNode;
  /** The Tabsbar, if the screen has one. */
  tabs?: ReactNode;
  /** Drawn over the whole shell: the command palette's scrim and dialog. */
  overlay?: ReactNode;
  /** The panes, laid out in the body row. */
  children?: ReactNode;
  className?: string;
}

export interface FirmShellProps extends ShellCommon {
  variant?: "firm";
  toolbar: ToolbarProps;
}

export interface PortalShellProps extends ShellCommon {
  variant: "portal";
  toolbar: PortalToolbarProps;
  /** The "Secured by" footer, which the firm turns on in ADM-10. Default off. */
  securedFooter?: boolean;
}

export type AppShellProps = FirmShellProps | PortalShellProps;

/** True for Ctrl K and Cmd K. */
function isGoChord(event: KeyboardEvent): boolean {
  return (event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "k";
}

export function AppShell(props: AppShellProps): JSX.Element {
  const {
    frame = false,
    embedded = false,
    height,
    record,
    tabs,
    overlay,
    children,
    className,
  } = props;
  const portal = props.variant === "portal";
  const onGo = props.variant === "portal" ? undefined : props.toolbar.onGo;
  useEffect(() => {
    if (portal || onGo === undefined) return undefined;
    const handle = (event: KeyboardEvent): void => {
      if (!isGoChord(event)) return;
      event.preventDefault();
      onGo();
    };
    document.addEventListener("keydown", handle);
    return () => {
      document.removeEventListener("keydown", handle);
    };
  }, [portal, onGo]);

  const framed = frame || embedded;
  const shell = (
    <div
      data-shell="app"
      data-variant={portal ? "portal" : "firm"}
      {...(framed ? { "data-frame": embedded ? "embedded" : "framed" } : {})}
      style={framed && height !== undefined ? { height } : undefined}
      className={cn(
        "relative flex flex-col bg-shell",
        framed
          ? "w-(--app-w) flex-none overflow-hidden rounded-window shadow-e1"
          : cn("h-dvh", !portal && "min-w-[1280px]"),
        className,
      )}
    >
      {props.variant === "portal" ? (
        <PortalToolbar {...props.toolbar} />
      ) : (
        <Toolbar {...props.toolbar} />
      )}
      {record}
      {tabs}
      <div
        data-shell="cols"
        className="flex min-h-0 flex-1 items-stretch gap-(--gutter-pane) px-(--edge-app) pt-(--gutter-pane) pb-(--edge-app)"
      >
        {children}
      </div>
      {props.variant === "portal" && props.securedFooter === true && <PortalFooter />}
      {overlay}
    </div>
  );
  if (!framed) return shell;
  return (
    <div
      data-shell="stage"
      className={cn(
        "flex items-start justify-center",
        embedded ? "min-h-[600px]" : "min-h-[calc(100vh-80px)] bg-presentation p-[40px]",
      )}
    >
      {shell}
    </div>
  );
}
