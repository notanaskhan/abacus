import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Segmented, type Opt } from "../components/tabs";
import { AppShell } from "../layout/app-shell";
import { Pane } from "../layout/pane";
import { SplitLayout } from "../layout/split-layout";
import { Tabsbar } from "../layout/tabsbar";
import type { ToolbarProps } from "../layout/toolbar";

// T5 CatalogLayout (F-05-T59; T5 handoff, Wave 0 Foundations #t5; C-11 §1, C-14 §1): the catalog
// grid behind Workbench › Agents and Connect. Under the toolbar 46, the tabsbar 50 (a centred
// Segmented: Sessions · Agents · Connect), on Agents a 44 sub-row with a LEFT-aligned small
// Segmented ("Library · My Agents"), then the columns padded 10 12 12 on the C-09 `library`
// preset: the 358 side pane (an optional 46 search row, the AboutCard, the CategoryList) beside the
// grid pane (header 46 with the status Picker at the left, the title centred and an optional
// search at the right) whose shell-coloured well holds three columns of cards, gap 12. Agents pad
// the well 10 14 14 (cards 210); Connect pads 14 on every side (tiles 212).

const TOOLBAR_H = 46;
const TABS_H = 50;
const SUBROW_H = 44;
/** The body row's padding: 10 above, 12 below. */
const PAD_H = 22;

export interface CatalogLayoutProps {
  toolbar: ToolbarProps;
  tabs: {
    options: readonly Opt[];
    active: string;
    onChange?: (label: string) => void;
    /** The tablist's accessible name: "Workbench" by default, "Knowledge" on KNW-01. */
    label?: string;
  };
  /** The 44 sub-row's small Segmented ("Library · My Agents"); Connect has none. */
  subRow?: {
    options: readonly Opt[];
    active: string;
    label: string;
    onChange?: (l: string) => void;
  };
  side: {
    /** The 46 search row: a SearchField and the round dark +. */
    search?: ReactNode;
    /** The AboutCard. */
    about: ReactNode;
    /** The CategoryList. */
    categories: ReactNode;
  };
  grid: {
    title: string;
    /** The status Picker at the left. */
    left?: ReactNode;
    /** A SearchField at the right (Connect). */
    right?: ReactNode;
    /** `agents` pads the well 10 14 14; `connect` pads 14 all round. */
    well?: "agents" | "connect";
    body: ReactNode;
  };
  /** An overlay over the frame (a confirm dialog's host). */
  overlay?: ReactNode;
  frame?: boolean;
  embedded?: boolean;
  height?: number;
  className?: string;
  /** Inside the app's own shell (a routed screen): the tabsbar and columns without a second
   * AppShell and toolbar; `toolbar`, `frame`, `embedded` and `height` are then ignored. */
  bare?: boolean;
}

export function CatalogLayout({
  toolbar,
  tabs,
  subRow,
  side,
  grid,
  overlay,
  frame = false,
  embedded = false,
  height,
  className,
  bare = false,
}: CatalogLayoutProps): JSX.Element {
  const chrome = TOOLBAR_H + TABS_H + (subRow === undefined ? 0 : SUBROW_H) + PAD_H;
  const tabsbar = (
    <>
      <Tabsbar
        label={tabs.label ?? "Workbench"}
        options={tabs.options}
        active={tabs.active}
        {...(tabs.onChange === undefined ? {} : { onChange: tabs.onChange })}
      />
      {subRow !== undefined && (
        <div
          data-catalog="sub-row"
          className="flex h-[44px] flex-none items-center px-(--edge-app)"
        >
          <Segmented
            size="small"
            label={subRow.label}
            options={subRow.options}
            active={subRow.active}
            {...(subRow.onChange === undefined ? {} : { onChange: subRow.onChange })}
          />
        </div>
      )}
    </>
  );
  const columns = (
    <div data-catalog="frame" className="flex min-h-0 min-w-0 flex-1">
      <SplitLayout
        preset="library"
        height={height === undefined ? "viewport" : height - chrome}
        narrow={false}
        className="w-full bg-transparent p-0"
      >
        {[
          <Pane key="side" header={false} className="min-h-0">
            <div data-catalog="side" className="flex min-h-0 flex-1 flex-col overflow-auto">
              {side.search !== undefined && (
                <div className="flex h-[46px] flex-none items-center gap-[8px] px-[10px] hairline-b">
                  {side.search}
                </div>
              )}
              {side.about}
              {side.categories}
            </div>
          </Pane>,
          <Pane
            key="grid"
            title={grid.title}
            {...(grid.left === undefined ? {} : { left: grid.left })}
            {...(grid.right === undefined ? {} : { right: grid.right })}
            className="min-h-0"
          >
            <div
              data-catalog="well"
              className={cn(
                "min-h-0 flex-1 overflow-auto bg-shell",
                grid.well === "connect" ? "p-[14px]" : "px-[14px] pt-[10px] pb-[14px]",
              )}
            >
              {grid.body}
            </div>
          </Pane>,
        ]}
      </SplitLayout>
    </div>
  );
  if (bare) {
    return (
      <div data-catalog="bare" className="relative flex min-h-0 flex-1 flex-col">
        {tabsbar}
        <div className="flex min-h-0 flex-1 px-(--edge-app) pt-(--gutter-pane) pb-(--edge-app)">
          {columns}
        </div>
        {overlay}
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
      {...(overlay === undefined ? {} : { overlay })}
      tabs={tabsbar}
    >
      {columns}
    </AppShell>
  );
}
