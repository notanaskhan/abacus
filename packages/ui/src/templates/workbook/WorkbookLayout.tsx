import { type JSX, type KeyboardEvent, type ReactNode, useId } from "react";
import type { Actor } from "../../attribution/actor";
import { HumanAction } from "../../attribution/human-action";
import { Button } from "../../components/button";
import { AgentRunningRow } from "../../components/states";
import { Segmented } from "../../components/tabs";
import { DataGrid } from "../../data/data-grid";
import { type TallyItem, TallyStrip } from "../../data/tally-strip";
import type { TableColumn, TableRow } from "../../data/types";
import { AppShell } from "../../layout/app-shell";
import type { ToolbarProps } from "../../layout/toolbar";
import { useMotion } from "../../motion";
import { cn } from "../../cn";
import type { TablePayload, WorkbookCopy, WorkbookPaneVM, WorkbookTallyItem, WorkbookVM } from "./types";

// T6 WorkbookLayout (F-06-T18; T6 and TPL-06 handoff, Wave 0 Foundations #t6; F-06.md §3 F5,
// §5.2): under the toolbar 46 and the record subbar 42, the tabsbar 50 holding two small
// SegmentedGroups at x12 in one row, the control bar 44 (a small view Segmented on the left, the
// view title centred absolutely, ghost "Open in Excel" and "Download" on the right), the tally
// strip 52 and the columns padded 10 12 12 (panes y244–848 in the 860 window). Statement panes are
// F-05's grammar; sized panes (452, by partner) sit in the PaneScroller, a labelled focusable
// region that the arrow keys move.
//
// Every figure is the server's (ADR-050): the kit lays out, formats through the grammar and adds
// nothing. Building is the agent's proposal in progress (INV-1): tally values and results read
// Pending, rows are skeletons under the running row, and Sign off… is drawn disabled saying why.
// T6 adopts no T18 behaviour: no editable cells, no agent columns. Export is the consumer's
// (ADR-042): Open in Excel and Download are callbacks. Calc tree (e) is F-06-T19's; the sign-off
// slots and their chips (d) are F-06-T20's.

/** The window chrome above the panes: toolbar, subbar, tabsbar, control bar, tally, padding. */
const CHROME = 46 + 42 + 50 + 44 + 52 + 22;

/** A sized pane and the gap after it: one arrow-key step of the scroller. */
const PANE_GAP = 10;

/** The skeleton rows a building pane draws (canvas `t6Skel`: seven, widths cycling by three). */
const SKELETON_ROWS = 7;
const LABEL_WIDTHS = ["46%", "62%", "38%"] as const;
const VALUE_WIDTHS = ["58%", "74%", "46%"] as const;
/** Each skeleton row's pulse starts 90 ms after the one above (55–70 ms rows reveal; canvas 90). */
const SKELETON_STAGGER_MS = 90;

export interface WorkbookLayoutProps {
  workbook: WorkbookVM;
  copy: WorkbookCopy;
  toolbar: ToolbarProps;
  /** The RecordHeader (subbar 42). */
  record: ReactNode;
  /** The record tabs and the selected tab's sub-tabs (a small SegmentedGroup), left at x12. */
  tabs?: ReactNode;
  onView?: (view: string) => void;
  onOpenInExcel?: () => void;
  onDownload?: () => void;
  /** An off pill's issue link or a variance exception's issue: the consumer opens the issue. */
  onOpenIssue?: (issue: string) => void;
  /** "Explain…" on an unexplained variance: the consumer opens its O1 editor. */
  onExplain?: (row: TableRow, columnKey: string) => void;
  /** The signed-in person and what they would sign off: draws "Sign off…" in the control bar. */
  signOff?: { actor: Actor; target: string; level?: string };
  /** Opens SHL-12 (P-04). The kit never creates a sign-off. */
  onOpenSignOff?: (target: string, level?: string) => void;
  frame?: boolean;
  embedded?: boolean;
  height?: number;
  className?: string;
}

/** The control bar (44): view Segmented left, the title centred on the bar, ghost exports right. */
export function ControlBar({
  views,
  view,
  title,
  label,
  copy,
  onView,
  onOpenInExcel,
  onDownload,
  children,
}: {
  views: WorkbookVM["views"];
  view: string;
  title: string;
  label: string;
  copy: Pick<WorkbookCopy, "openInExcel" | "download">;
  onView?: ((view: string) => void) | undefined;
  onOpenInExcel?: (() => void) | undefined;
  onDownload?: (() => void) | undefined;
  /** After the exports: the sign-off control. */
  children?: ReactNode;
}): JSX.Element {
  return (
    <div
      data-workbook="control-bar"
      className="relative flex h-[44px] flex-none items-center gap-[6px] px-[12px]"
    >
      <Segmented
        size="small"
        label={label}
        options={views}
        active={view}
        {...(onView === undefined ? {} : { onChange: onView })}
      />
      <span className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-pane font-medium whitespace-nowrap">
        {title}
      </span>
      <span className="flex-1" />
      <Button variant="ghost" size="sm" icon="file-spreadsheet" onClick={onOpenInExcel}>
        {copy.openInExcel}
      </Button>
      <Button variant="ghost" size="sm" icon="download" onClick={onDownload}>
        {copy.download}
      </Button>
      {children}
    </div>
  );
}

/** Sized panes side by side in a labelled, focusable region; ← and → move it one pane. */
export function PaneScroller({
  label,
  step,
  children,
}: {
  label: string;
  /** px moved per arrow key: the pane width plus the gap. */
  step: number;
  children: ReactNode;
}): JSX.Element {
  const animate = useMotion();
  const onKey = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    event.currentTarget.scrollBy({
      left: event.key === "ArrowRight" ? step : -step,
      behavior: animate ? "smooth" : "auto",
    });
  };
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      data-workbook="scroller"
      onKeyDown={onKey}
      className="flex min-w-0 flex-1 gap-[10px] overflow-x-auto outline-offset-2"
    >
      {children}
    </div>
  );
}

/** Building: values and results wait on the run. A card's value, result or sign-offs become
 * Pending, a running card keeps its spinner, and no card links anywhere. */
function pendingTally(items: readonly WorkbookTallyItem[]): TallyItem[] {
  return items.map((item) =>
    "running" in item
      ? { label: item.label, running: item.running }
      : { label: item.label, tally: "pending" },
  );
}

function tallyWithLinks(
  items: readonly WorkbookTallyItem[],
  onOpenIssue: ((issue: string) => void) | undefined,
): TallyItem[] {
  return items.map((item) => {
    const { issue, ...card } = item;
    if (issue === undefined || onOpenIssue === undefined) return card;
    return {
      ...card,
      link: {
        text: `Issue ${issue}`,
        onClick: () => {
          onOpenIssue(issue);
        },
      },
    };
  });
}

/** The 30 column heads, the running row and seven skeleton rows: the pane keeps its geometry. */
function BuildingTable({
  columns,
  label,
}: {
  columns: readonly TableColumn[];
  label: string;
}): JSX.Element {
  const template = columns
    .map((c, i) => (i === 0 ? "minmax(0,1fr)" : `${String(c.width ?? 120)}px`))
    .join(" ");
  return (
    <div>
      <div
        role="row"
        style={{ gridTemplateColumns: template }}
        className="grid h-[30px] items-center border-b-[0.5px] border-hair bg-band-hd text-th font-medium text-ink-3"
      >
        {columns.map((c, i) => (
          <span
            key={c.key}
            role="columnheader"
            className={cn("px-[16px]", i === 0 ? "text-left" : "text-right")}
          >
            {c.header}
          </span>
        ))}
      </div>
      <AgentRunningRow state="run" title={label} className="border-b-[0.5px] border-hair" />
      {Array.from({ length: SKELETON_ROWS }, (_, i) => (
        <div
          key={i}
          data-workbook="skeleton-row"
          aria-hidden="true"
          style={{ gridTemplateColumns: template }}
          className="grid h-[26px] items-center border-b-[0.5px] border-hair"
        >
          {columns.map((c, j) => (
            <span
              key={c.key}
              className={cn(
                "flex px-[16px]",
                j === 0 ? "justify-start" : "justify-end",
                j === 0 && i % 3 !== 0 && "pl-[41px]",
              )}
            >
              <span
                style={{
                  width:
                    j === 0 ? LABEL_WIDTHS[i % 3] : VALUE_WIDTHS[(i + j) % 3],
                  animationDelay: `${String(i * SKELETON_STAGGER_MS)}ms`,
                }}
                className="motion-pulse block h-[8px] rounded-full bg-nested"
              />
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

function StatementPane({
  pane,
  table,
  building,
  onOpenIssue,
  onExplain,
}: {
  pane: WorkbookPaneVM;
  table: TablePayload;
  building: { label: string } | undefined;
  onOpenIssue: ((issue: string) => void) | undefined;
  onExplain: ((row: TableRow, columnKey: string) => void) | undefined;
}): JSX.Element {
  const issueOf = (row: TableRow): string | undefined =>
    Object.values(row.cells).find((cell) => cell?.variance?.exception !== undefined)?.variance
      ?.exception?.issue;
  return (
    <section
      data-workbook="pane"
      aria-label={pane.title ?? table.label}
      aria-busy={building === undefined ? undefined : true}
      style={pane.width === undefined ? undefined : { width: pane.width }}
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-pane bg-card shadow-e2",
        pane.width === undefined ? "min-w-0 flex-1" : "flex-none",
      )}
    >
      {pane.title !== undefined && (
        <h3 className="flex h-(--pane-hd-h) flex-none items-center justify-center border-b-[0.5px] border-hair text-pane font-medium">
          {pane.title}
        </h3>
      )}
      <div className="min-h-0 flex-1 overflow-auto">
        {building === undefined ? (
          <DataGrid
            label={table.label}
            grammar="statement"
            columns={table.columns}
            rows={table.rows}
            {...(onExplain === undefined ? {} : { onExplain })}
            {...(onOpenIssue === undefined
              ? {}
              : {
                  onIssue: (row: TableRow) => {
                    const issue = issueOf(row);
                    if (issue !== undefined) onOpenIssue(issue);
                  },
                })}
          />
        ) : (
          <BuildingTable columns={table.columns} label={building.label} />
        )}
      </div>
      {table.footnote !== undefined && building === undefined && (
        <p className="flex-none px-[16px] pt-[10px] pb-[12px] text-meta text-ink-3">
          {table.footnote}
        </p>
      )}
    </section>
  );
}

export function WorkbookLayout({
  workbook,
  copy,
  toolbar,
  record,
  tabs,
  onView,
  onOpenInExcel,
  onDownload,
  onOpenIssue,
  onExplain,
  signOff,
  onOpenSignOff,
  frame = false,
  embedded = false,
  height,
  className,
}: WorkbookLayoutProps): JSX.Element {
  const reasonId = useId();
  const { building } = workbook;
  const tally =
    building === undefined
      ? tallyWithLinks(workbook.tally, onOpenIssue)
      : pendingTally(workbook.tally);
  // F-06-T19 draws `grid` and `calc`; until then only statement panes render.
  const statements = workbook.panes.filter(
    (p): p is WorkbookPaneVM & { table: TablePayload } =>
      p.kind === "statement" && p.table !== undefined,
  );
  const sized = statements.filter((p) => p.width !== undefined);
  const panes = statements.map((pane, i) => (
    <StatementPane
      key={`${pane.table.label}:${String(i)}`}
      pane={pane}
      table={pane.table}
      building={building}
      onOpenIssue={onOpenIssue}
      onExplain={onExplain}
    />
  ));
  const step = (sized[0]?.width ?? 0) + PANE_GAP;
  const panesHeight = height === undefined ? undefined : height - CHROME;

  const signOffControl =
    signOff === undefined || onOpenSignOff === undefined ? null : (
      <>
        <HumanAction
          verb="Sign off"
          opensDialog
          actor={signOff.actor}
          variant="secondary"
          size="sm"
          disabled={building !== undefined}
          {...(building === undefined
            ? {
                onClick: () => {
                  onOpenSignOff(signOff.target, signOff.level);
                },
              }
            : { "aria-describedby": reasonId })}
        />
        {building !== undefined && (
          <span id={reasonId} className="sr-only">
            {building.label}
          </span>
        )}
      </>
    );

  return (
    <AppShell
      toolbar={toolbar}
      frame={frame}
      embedded={embedded}
      {...(height === undefined ? {} : { height })}
      {...(className === undefined ? {} : { className })}
      record={record}
      tabs={
        <>
          <div
            data-shell="tabsbar"
            data-workbook="tabsbar"
            className="flex h-[50px] flex-none flex-nowrap items-center gap-[8px] overflow-hidden px-[12px]"
          >
            {tabs}
          </div>
          <ControlBar
            views={workbook.views}
            view={workbook.view}
            title={workbook.title}
            label={copy.views}
            copy={copy}
            onView={onView}
            onOpenInExcel={onOpenInExcel}
            onDownload={onDownload}
          >
            {signOffControl}
          </ControlBar>
          <div data-workbook="tally" className="h-[52px] flex-none px-[12px]">
            <TallyStrip items={tally} />
          </div>
        </>
      }
    >
      {/* The shell's columns pad 10 12 12: the panes sit at y244–848 in the 860 window. */}
      <div
        data-template="t6"
        data-workbook="columns"
        data-state={building === undefined ? "built" : "building"}
        style={panesHeight === undefined ? undefined : { height: panesHeight }}
        className="flex min-h-0 min-w-0 flex-1 gap-[10px]"
      >
        {sized.length > 0 ? (
          <PaneScroller label={copy.scroller} step={step}>
            {panes}
          </PaneScroller>
        ) : (
          panes
        )}
      </div>
    </AppShell>
  );
}
