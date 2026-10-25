import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { AppShell } from "../layout/app-shell";
import { Pane } from "../layout/pane";
import { SplitLayout } from "../layout/split-layout";
import type { ToolbarProps } from "../layout/toolbar";

// T8 InboxLayout (F-05-T56; T8 handoff, Wave 0 Foundations #t8): the firm inbox, master and
// detail. Under the toolbar 46, the filter bar 50 with a −10 bottom margin ("← All Messages" and the
// split filter chips, amber once set), then the columns padded 10 12 12 on the C-09 `inbox` preset:
// the 392 rail (header 44 with the mailbox pill, "Inbox" and the ignored and filed toggles; the
// search row 44; the rows) beside the reading pane (header 44, then the messages newest first).
// Panes run y96–848, 752 tall in the 860 window. The C-15/C-18 File kit fills the slots.

/** The shell above and below the panes: toolbar 46, filter bar 50 − 10, padding 10 + 12. */
const CHROME = 46 + 40 + 22;

export interface InboxLayoutProps {
  toolbar: ToolbarProps;
  /** The filter bar's chips: "← All Messages", Client, Status, Received, Channel. */
  filters: ReactNode;
  rail: {
    /** The header's left (the mailbox pill) and right (the ignored and filed toggles). */
    left?: ReactNode;
    right?: ReactNode;
    title?: string;
    /** The 44 search row under the header. */
    search?: ReactNode;
    body: ReactNode;
  };
  reading: { header?: ReactNode; body: ReactNode };
  frame?: boolean;
  embedded?: boolean;
  height?: number;
  className?: string;
}

/** The T8 frame: the filter bar, the 392 rail and the reading pane. */
export function InboxLayout({
  toolbar,
  filters,
  rail,
  reading,
  frame = false,
  embedded = false,
  height,
  className,
}: InboxLayoutProps): JSX.Element {
  return (
    <AppShell
      toolbar={toolbar}
      frame={frame}
      embedded={embedded}
      {...(height === undefined ? {} : { height })}
      {...(className === undefined ? {} : { className })}
      tabs={
        <div
          data-inbox="filters"
          role="toolbar"
          aria-label="Filters"
          className="-mb-[10px] flex h-(--tabs-h) flex-none items-center gap-[8px] px-[12px]"
        >
          {filters}
        </div>
      }
    >
      <div data-inbox="frame" className="flex min-h-0 min-w-0 flex-1">
        <SplitLayout
          preset="inbox"
          height={height === undefined ? "viewport" : height - CHROME}
          narrow={false}
          className="w-full bg-transparent p-0"
        >
          {[
            <Pane
              key="rail"
              title={rail.title ?? "Inbox"}
              {...(rail.left === undefined ? {} : { left: rail.left })}
              {...(rail.right === undefined ? {} : { right: rail.right })}
              className="min-h-0"
            >
              <div data-inbox="rail" className="flex min-h-0 flex-1 flex-col">
                {rail.search !== undefined && (
                  <div className="flex h-[44px] flex-none items-center gap-[8px] px-[12px] hairline-b">
                    {rail.search}
                  </div>
                )}
                <div className="min-h-0 flex-1 overflow-auto pt-[8px]">{rail.body}</div>
              </div>
            </Pane>,
            <Pane key="reading" header={false} className="min-h-0">
              <div data-inbox="reading" className="flex min-h-0 flex-1 flex-col">
                {reading.header !== undefined && (
                  <div
                    className={cn(
                      "flex h-(--pane-hd-h) flex-none items-center px-[12px] hairline-b",
                    )}
                  >
                    {reading.header}
                  </div>
                )}
                <div className="min-h-0 flex-1 overflow-auto">{reading.body}</div>
              </div>
            </Pane>,
          ]}
        </SplitLayout>
      </div>
    </AppShell>
  );
}
