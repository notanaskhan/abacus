import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { AppShell } from "../layout/app-shell";
import { Pane } from "../layout/pane";
import { SplitLayout } from "../layout/split-layout";
import type { ToolbarProps } from "../layout/toolbar";
import { MatchScope } from "../tracing/match";
import type { MatchStore } from "../tracing/match-store";
import type { CitationPayload } from "../tracing/types";

// T9 QueueDetailLayout (F-05-T55; T9 handoff, Wave 0 Foundations #t9): a queue of issues, the
// selected issue's detail, and the evidence it points at, in one MatchScope so a workbook cell or a
// linked entity lights its source (E1). Three presets, on the C-09 SplitLayout presets of the same
// names (chapter 04 §3.11), under the toolbar 46:
//
//   issues-individual  subbar 42 + tabsbar 44; panes 706 tall: a 546 pane whose 8px shell well
//                      holds the 262 queue card and the flex detail card (radius 10, e1), beside
//                      the viewer 433 and the sheet 377
//   close-review       close header 42 + tabs 50; panes 700 tall: one 790 pane split 310 | 480 by
//                      a hairline, beside the register 576
//   issues-entity      subbar 42 + tabsbar 50; panes 700 tall: the 470 queue pane ("Issues")
//                      beside the 896 detail pane ("Issue") with the instruction composer
//
// The detail's footer is pinned under it (padding 10, gap 8). The template draws no issue data:
// the C-17 Issue kit fills the slots.

export type QueuePreset = "issues-individual" | "close-review" | "issues-entity";

export const QUEUE_PRESETS: readonly QueuePreset[] = [
  "issues-individual",
  "close-review",
  "issues-entity",
];

/** The shell's own height above and below the panes: toolbar, record and tabs, padding 10 + 12. */
const CHROME: Record<QueuePreset, number> = {
  "issues-individual": 46 + 42 + 44 + 22,
  "close-review": 46 + 92 + 22,
  "issues-entity": 46 + 42 + 50 + 22,
};

/** The queue's width inside its pane (individual: the card; close: the left of the split). */
const QUEUE_WIDTH: Record<Exclude<QueuePreset, "issues-entity">, number> = {
  "issues-individual": 262,
  "close-review": 310,
};

export interface QueueDetailLayoutProps {
  preset: QueuePreset;
  toolbar: ToolbarProps;
  /** The record subbar (a RecordHeader), or the close header with its tabs. */
  record: ReactNode;
  /** The tabsbar (none for close-review, whose header carries its tabs). */
  tabs?: ReactNode;
  /** The queue pane's header: left (search, filter), title, right (Download, + Issue…, Show
   * resolved). */
  queue: { title?: string; left?: ReactNode; right?: ReactNode; body: ReactNode };
  /** The detail: its body, its pinned footer and (entity) the instruction composer; `right` sits
   * in the entity detail pane's header (TPL-09c's Resolve). */
  detail: {
    title?: string;
    right?: ReactNode;
    body: ReactNode;
    footer?: ReactNode;
    composer?: ReactNode;
  };
  /** The evidence panes after the queue: viewer and sheet (individual), the register (close). */
  evidence?: readonly ReactNode[];
  store?: MatchStore<CitationPayload>;
  frame?: boolean;
  embedded?: boolean;
  /** Routed inside the app's shell, which already draws the toolbar: the record, tabs and panes
   * alone (HOME-02 at `/home/approvals`; I-01-T16). `toolbar` is then ignored. */
  bare?: boolean;
  height?: number;
  className?: string;
}

function DetailColumn({
  detail,
  className,
}: {
  detail: QueueDetailLayoutProps["detail"];
  className?: string;
}): JSX.Element {
  return (
    <div data-queue-part="detail" className={cn("flex min-h-0 min-w-0 flex-col", className)}>
      <div className="min-h-0 flex-1 overflow-auto">{detail.body}</div>
      {detail.composer !== undefined && (
        <div className="flex-none px-[10px] pb-[10px]">{detail.composer}</div>
      )}
      {detail.footer !== undefined && (
        <div className="flex-none p-[10px] hairline-t">{detail.footer}</div>
      )}
    </div>
  );
}

/** The T9 frame: queue, detail and evidence under three presets. */
export function QueueDetailLayout({
  preset,
  toolbar,
  record,
  tabs,
  queue,
  detail,
  evidence = [],
  store,
  frame = false,
  embedded = false,
  bare = false,
  height,
  className,
}: QueueDetailLayoutProps): JSX.Element {
  const queuePane = (
    <Pane
      key="queue"
      title={queue.title ?? "Issues"}
      {...(queue.left === undefined ? {} : { left: queue.left })}
      {...(queue.right === undefined ? {} : { right: queue.right })}
      className="min-h-0"
    >
      {preset === "issues-individual" ? (
        <div data-queue-part="well" className="flex min-h-0 flex-1 gap-[8px] bg-shell p-[8px]">
          <div
            data-queue-part="queue"
            style={{ width: QUEUE_WIDTH[preset] }}
            className="min-h-0 flex-none overflow-auto rounded-nested bg-card shadow-e1"
          >
            {queue.body}
          </div>
          <DetailColumn
            detail={detail}
            className="flex-1 overflow-hidden rounded-nested bg-card shadow-e1"
          />
        </div>
      ) : preset === "close-review" ? (
        <div data-queue-part="split" className="flex min-h-0 flex-1">
          <div
            data-queue-part="queue"
            style={{ width: QUEUE_WIDTH[preset] }}
            className="min-h-0 flex-none overflow-auto hairline-r"
          >
            {queue.body}
          </div>
          <DetailColumn detail={detail} className="flex-1" />
        </div>
      ) : (
        <div data-queue-part="queue" className="min-h-0 flex-1 overflow-auto">
          {queue.body}
        </div>
      )}
    </Pane>
  );
  const panes: ReactNode[] =
    preset === "issues-entity"
      ? [
          queuePane,
          <Pane
            key="detail"
            title={detail.title ?? "Issue"}
            {...(detail.right === undefined ? {} : { right: detail.right })}
            className="min-h-0"
          >
            <DetailColumn detail={detail} className="flex-1" />
          </Pane>,
        ]
      : [
          queuePane,
          ...evidence.map((node, i) => (
            // The evidence panes are positional: viewer then sheet, or the register.
            <div
              key={`evidence-${String(i)}`}
              data-queue-part="evidence"
              className="flex min-h-0 min-w-0 flex-1"
            >
              {node}
            </div>
          )),
        ];
  const body = (
    <MatchScope {...(store === undefined ? {} : { store })}>
      <div data-queue={preset} className="flex min-h-0 min-w-0 flex-1">
        <SplitLayout
          preset={preset}
          height={height === undefined ? "viewport" : height - CHROME[preset]}
          narrow={false}
          className="w-full bg-transparent p-0"
        >
          {panes}
        </SplitLayout>
      </div>
    </MatchScope>
  );
  if (bare) {
    return (
      <div data-queue-shell="bare" className={cn("flex min-h-0 flex-1 flex-col", className)}>
        {record}
        {tabs}
        <div className="flex min-h-0 flex-1 px-(--edge-app) pt-(--gutter-pane) pb-(--edge-app)">
          {body}
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
      record={record}
      {...(tabs === undefined ? {} : { tabs })}
    >
      {body}
    </AppShell>
  );
}
