import { type JSX, type ReactNode, useId, useState } from "react";
import { cn } from "../cn";
import { IconButton } from "../components/button";
import { LiveDot } from "../components/motion";
import { Segmented } from "../components/tabs";
import { type EmptyContent, type ViewState, ViewStateBody } from "../components/view-state";
import { AppShell } from "../layout/app-shell";
import { PaneHeader } from "../layout/pane";
import { type AuditRecordHeaderProps, RecordHeader } from "../layout/record-header";
import type { ToolbarProps } from "../layout/toolbar";

// T2 RecordCockpit (F-05-T40; T2 handoff, Wave 0 Foundations #t2): the record template 44 boards
// build on. Under the toolbar and the 59 audit record bar, the body row holds three panes:
//
//   rail    330, the C-03 RecordRail (a slot: the screen passes <RecordRail>)
//   canvas  flex: 696 beside the dock, 1036 without it (to x1388 in the 1400 window)
//   dock    330, switching Agent · Viewer · Notes; the layout chip in the record bar shows or
//           hides it
//
// The template is a frame. What the canvas and the dock hold is the screen's (the Workpaper and
// Data kits, the C-12 run rows, the C-08 viewer); the template owns the geometry, the dock's
// header (the live dot while a run executes, the Run pill when none has), the composer slot and
// the canvas's ViewState. Rail rows say their state in words beside a disc (C-03), never colour.

export const DOCK_VIEWS = ["Agent", "Viewer", "Notes"] as const;
export type DockView = (typeof DOCK_VIEWS)[number];

export interface CockpitCanvas {
  /** The left-aligned 14.5 / 500 title ("Trial Balance"). */
  title: string;
  /** The header's right cluster: white e1 pills ("Edit", "Sign off…", "Source Docs"). */
  actions?: ReactNode;
  /** The optional 42 control row: small segmented tabs left, "Open in Excel" right. */
  controls?: ReactNode;
  /** The body sits on the shell well (block cards) rather than white. */
  well?: boolean;
  /** The pinned footer ("Citations (3)", "Procedures (3)"). */
  footer?: ReactNode;
  /** Loading, empty, error ... (C-20); `ready` renders `children`. Default ready. */
  state?: ViewState;
  /** What the empty canvas says (T2e). */
  empty?: EmptyContent;
  children?: ReactNode;
}

export interface CockpitDock {
  view: DockView;
  /** The views this dock offers; one view draws its name as the title instead of the switch. */
  views?: readonly DockView[];
  /** A single-purpose dock's own title in place of the view's name ("Request" on BND-02). */
  title?: string;
  onView?: (view: DockView) => void;
  /** A run is executing: the 8px olive live dot before the switch (T2b). */
  live?: boolean;
  /** The header's right cluster: the dark 32 "Run" pill when no run has started (T2a). */
  action?: ReactNode;
  /** Pinned under the body, margin 10: the 38 composer for the Agent view. */
  composer?: ReactNode;
  children?: ReactNode;
}

export interface RecordCockpitProps {
  /** The firm toolbar. Without one the cockpit draws inside a shell that already has it (a routed
   * screen in the workspace): no window, the same bar, tabs and columns. */
  toolbar?: ToolbarProps;
  /** The audit record bar; the template wires its layout chip to the dock. */
  record?: Omit<AuditRecordHeaderProps, "variant" | "onLayout">;
  /** A record's own bar in place of the audit one (chrome takes slots, plan 04 §4.5 rule 5): the
   * 42 settings-style subbar of a binder or a client record. Wins over `record`. */
  header?: ReactNode;
  /** The 50 tabsbar under the bar (a `Tabsbar`). */
  tabs?: ReactNode;
  /** The 330 rail: a `RecordRail`. */
  rail: ReactNode;
  canvas: CockpitCanvas;
  /** No dock: the canvas runs to the right edge. */
  dock?: CockpitDock;
  /** Controlled dock visibility (the layout chip). Uncontrolled from `defaultDockOpen`. */
  dockOpen?: boolean;
  defaultDockOpen?: boolean;
  onDockOpenChange?: (open: boolean) => void;
  /** Presentation only (the gallery): the 1400 window on the presentation ground. */
  frame?: boolean;
  embedded?: boolean;
  /** A fixed window height in px, framed only (860 in the handoff). */
  height?: number;
  className?: string;
}

/** The T2 frame: rail, canvas and dock under the audit record bar. */
export function RecordCockpit({
  toolbar,
  record,
  header,
  tabs,
  rail,
  canvas,
  dock,
  dockOpen,
  defaultDockOpen = true,
  onDockOpenChange,
  frame = false,
  embedded = false,
  height,
  className,
}: RecordCockpitProps): JSX.Element {
  const [ownOpen, setOwnOpen] = useState(defaultDockOpen);
  const open = dock !== undefined && (dockOpen ?? ownOpen);
  const toggle = (): void => {
    const next = !(dockOpen ?? ownOpen);
    setOwnOpen(next);
    onDockOpenChange?.(next);
  };
  const bar =
    header ??
    (record === undefined ? undefined : (
      <RecordHeader
        {...record}
        variant="audit"
        {...(dock === undefined ? {} : { onLayout: toggle })}
      />
    ));
  const panes = (
    <>
      <div data-cockpit="rail" className="flex w-(--rail-w) flex-none flex-col">
        {rail}
      </div>
      <Canvas canvas={canvas} />
      {open && <Dock dock={dock} />}
    </>
  );
  if (toolbar === undefined) {
    // Inside a shell that already draws the toolbar (the app's workspace): the bar, the tabs and
    // the same three columns, without a second window. In the shell's body it takes back the
    // body's padding, so the bar spans the window under the toolbar as AppShell's `record` slot
    // does (audit bar 46–105, panes from 115) and the columns carry the insets themselves.
    return (
      <div
        data-cockpit="bare"
        className={cn(
          "flex min-h-0 flex-1 flex-col in-data-[shell=cols]:-mx-(--edge-app) in-data-[shell=cols]:-mt-(--gutter-pane) in-data-[shell=cols]:-mb-(--edge-app)",
          className,
        )}
        {...(height === undefined ? {} : { style: { height } })}
      >
        {bar}
        {tabs}
        <div
          data-shell="cols"
          className="flex min-h-0 flex-1 items-stretch gap-(--gutter-pane) pt-(--gutter-pane) in-data-[shell=cols]:px-(--edge-app) in-data-[shell=cols]:pb-(--edge-app)"
        >
          {panes}
        </div>
      </div>
    );
  }
  return (
    <AppShell
      toolbar={toolbar}
      frame={frame}
      embedded={embedded}
      {...(height === undefined ? {} : { height })}
      {...(className === undefined ? {} : { className })}
      record={bar}
      {...(tabs === undefined ? {} : { tabs })}
    >
      {panes}
    </AppShell>
  );
}

function Canvas({ canvas }: { canvas: CockpitCanvas }): JSX.Element {
  const id = useId();
  const state = canvas.state ?? { kind: "ready" };
  return (
    <section
      data-cockpit="canvas"
      aria-labelledby={id}
      className="pane flex min-w-0 flex-[1_1_0%] flex-col overflow-hidden"
    >
      <PaneHeader
        title={canvas.title}
        titleAlign="left"
        titleId={id}
        {...(canvas.actions === undefined ? {} : { right: canvas.actions })}
      />
      {canvas.controls !== undefined && state.kind === "ready" && (
        <div
          data-cockpit="controls"
          className="flex h-[42px] flex-none items-center gap-[8px] px-[12px]"
        >
          {canvas.controls}
        </div>
      )}
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-auto",
          canvas.well === true && state.kind === "ready" && "bg-shell",
        )}
      >
        <ViewStateBody
          state={state}
          rows="card"
          empty={canvas.empty ?? { title: `${canvas.title} is empty` }}
          noun={canvas.title.toLowerCase()}
        >
          {canvas.children}
        </ViewStateBody>
      </div>
      {canvas.footer !== undefined && state.kind === "ready" && (
        <div
          data-cockpit="footer"
          className="flex flex-none items-center gap-[8px] px-[14px] py-[11px] hairline-t"
        >
          {canvas.footer}
        </div>
      )}
    </section>
  );
}

function Dock({ dock }: { dock: CockpitDock }): JSX.Element {
  const views = dock.views ?? DOCK_VIEWS;
  const id = useId();
  const switchable = views.length > 1;
  return (
    <section
      data-cockpit="dock"
      data-view={dock.view}
      aria-label={`${dock.title ?? dock.view} dock`}
      className="pane flex w-(--dock-w) flex-none flex-col overflow-hidden"
    >
      <div
        data-shell="pane-header"
        className="relative flex h-(--pane-hd-h) flex-none items-center gap-[8px] bg-card px-(--gutter-pane) hairline-b"
      >
        {dock.live === true && (
          <span data-cockpit="live" className="flex flex-none pl-[4px]">
            <LiveDot />
            <span className="sr-only">Run in progress</span>
          </span>
        )}
        <div className="flex min-w-0 flex-1 justify-center">
          {switchable ? (
            <Segmented
              size="small"
              label="Dock"
              options={views}
              active={dock.view}
              onChange={(label) => dock.onView?.(label as DockView)}
            />
          ) : (
            <h2 id={id} className="truncate text-pane font-medium tracking-[-0.012em]">
              {dock.title ?? dock.view}
            </h2>
          )}
        </div>
        {dock.action !== undefined && (
          <div className="flex flex-none items-center gap-[6px]">{dock.action}</div>
        )}
      </div>
      {/* A scrolling region a keyboard can reach (axe scrollable-region-focusable), as Pane's. */}
      <div
        role="region"
        aria-label={`${dock.title ?? dock.view} content`}
        tabIndex={0}
        className="flex min-h-0 flex-1 flex-col overflow-auto"
      >
        {dock.children}
      </div>
      {dock.composer !== undefined && (
        <div data-cockpit="composer" className="flex-none p-[10px]">
          {dock.composer}
        </div>
      )}
    </section>
  );
}

export interface DockComposerProps {
  /** "Message Accrued Agent". */
  placeholder: string;
  value?: string;
  onChange?: (value: string) => void;
  onSend?: (value: string) => void;
}

/** The dock's compact composer: a 38 nested pill with a round send button. */
export function DockComposer({
  placeholder,
  value,
  onChange,
  onSend,
}: DockComposerProps): JSX.Element {
  const [own, setOwn] = useState("");
  const text = value ?? own;
  const send = (): void => {
    if (text.trim() === "") return;
    onSend?.(text);
    if (value === undefined) setOwn("");
  };
  return (
    <form
      data-cockpit="composer-pill"
      className="flex h-[38px] items-center gap-[6px] rounded-pill bg-nested pr-[6px] pl-[14px] inset-shadow-hair"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <input
        aria-label={placeholder}
        placeholder={placeholder}
        value={text}
        onChange={(event) => {
          setOwn(event.target.value);
          onChange?.(event.target.value);
        }}
        className="min-w-0 flex-1 bg-transparent text-body text-ink outline-offset-2 placeholder:text-ink-3"
      />
      <IconButton icon="arrow-right" label="Submit message" variant="white" type="submit" />
    </form>
  );
}
