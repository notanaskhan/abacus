import { ChevronDown } from "lucide-react";
import { type JSX, type ReactNode } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { SearchField } from "../components/inputs";
import { EmptyState, SkeletonRows } from "../components/states";
import { UnderlineTabs } from "../components/tabs";
import { Drawer } from "../overlays/drawer";
import { SheetGrid } from "../sheet/SheetGrid";
import type { SheetGridProps, SheetGridRow } from "../sheet/types";
import { type SignOffChip, SignOffSlotChips } from "../signoff/SignOffSlots";

// SheetLayout (F-08-T08; F-08 §3 A4; T18 a-i). The L1 frame around SheetGrid: the 44 px sheet
// toolbar, the grid with its 30 px status bar, a 64 px P · R column of C-25 slots, presence slots
// and the O2 480 row drawer. `cockpit` (T18b) holds the grid to a 696 px canvas that scrolls
// sideways with select and Key frozen, beside the dock. The kit never signs: a P or R slot calls
// `onOpenSignOff(rowKeys, level)` and nothing else, and the agent never has a slot. No API client,
// router or domain words: everything arrives in typed view models and slots.

export type SheetLayoutVariant = "full" | "cockpit";
export type SheetLayoutView = "ready" | "empty" | "loading";
export type SignOffLevel = "P" | "R";

/** The drawer's tabs, in order (T18f). */
export const ROW_DRAWER_TABS = [
  "Details",
  "Comments",
  "Agents",
  "Evidence",
  "Requests",
  "To-dos",
] as const;
export type RowDrawerTab = (typeof ROW_DRAWER_TABS)[number];

/** T18h, verbatim. */
export const SHEET_EMPTY = {
  title: "No rows yet.",
  body: "Rows appear from the procedure session or when you add them.",
  action: "Add row",
} as const;

export const CANVAS_COCKPIT = 696;
export const TOOLBAR_H = 44;
export const PR_W = 64;
export const DRAWER_W = 480;

export interface SheetToolbar {
  /** The view picker's label ("Default view"). */
  view: string;
  savedViews?: readonly string[];
  /** Active filters: "Filter · n", amber when above zero (T18c). */
  filters: number;
  search: string;
  onSearch: (value: string) => void;
  onPickView?: () => void;
  onSavedView?: (name: string) => void;
  onAddView?: () => void;
  onFilter?: () => void;
  onClearFilters?: () => void;
  onColumns?: () => void;
  onSignOffs?: () => void;
  onAgents?: () => void;
  onComments?: () => void;
}

export interface SheetRowSignOffs {
  /** The preparer's (P) and reviewer's (R) current sign-offs on the row; the agent never signs. */
  P?: SignOffChip;
  R?: SignOffChip;
}

export interface SheetRowDrawer {
  rowKey: string;
  title: string;
  tab: RowDrawerTab;
  onTab: (tab: RowDrawerTab) => void;
  onClose: () => void;
  /** Each tab's body: C-29 comments, C-30 to-dos and the rest come from their epics (P-05). */
  slots: Partial<Record<RowDrawerTab, ReactNode>>;
}

export interface SheetLayoutProps {
  variant: SheetLayoutVariant;
  view: SheetLayoutView;
  toolbar: SheetToolbar;
  grid: SheetGridProps;
  /** P and R per row key; rows without a sign-off show the open slots. */
  signOffs?: Readonly<Record<string, SheetRowSignOffs>>;
  /** Open the consumer's sign-off modal for these rows at this level. The kit never signs. */
  onOpenSignOff: (rowKeys: readonly string[], level: SignOffLevel) => void;
  /** Who else is in the sheet (avatars from the presence epic). */
  presence?: ReactNode;
  drawer?: SheetRowDrawer;
  /** The cockpit's dock (T18b), right of the 696 px canvas. */
  dock?: ReactNode;
  onAddRow?: () => void;
}

const SLOT_COPY = {
  label: "Sign-offs",
  changedAfter: "Changed after sign-off",
  open: (name: string, level: string) => `${name}, ${level}: open sign-off`,
};

function SignOffCell({
  row,
  signed,
  onOpenSignOff,
}: {
  row: SheetGridRow;
  signed: SheetRowSignOffs | undefined;
  onOpenSignOff: SheetLayoutProps["onOpenSignOff"];
}): JSX.Element {
  return (
    <span className="flex items-center gap-[4px]" data-pr-slots="">
      {(["P", "R"] as const).map((level) => {
        const chip = signed?.[level];
        if (chip !== undefined) {
          return (
            <SignOffSlotChips
              key={level}
              target={row.key}
              slots={[{ ...chip, level }]}
              copy={SLOT_COPY}
              onOpenSignOff={() => {
                onOpenSignOff([row.key], level);
              }}
            />
          );
        }
        return (
          <button
            key={level}
            type="button"
            aria-label={`${level} sign-off for ${row.key}`}
            data-slot-level={level}
            className="flex size-[22px] items-center justify-center rounded-pill text-micro font-medium text-ink-3 inset-ring-[0.5px] inset-ring-hair hover:bg-nested"
            onClick={() => {
              onOpenSignOff([row.key], level);
            }}
          >
            {level}
          </button>
        );
      })}
    </span>
  );
}

function Toolbar({ toolbar }: { toolbar: SheetToolbar }): JSX.Element {
  const t = toolbar;
  const ghost =
    "h-[28px] rounded-pill px-[10px] text-dense font-medium text-ink-2 hover:bg-nested";
  return (
    <div
      data-sheet-toolbar=""
      style={{ height: TOOLBAR_H }}
      className="flex items-center gap-[6px] border-b border-hair bg-card px-[10px]"
    >
      <button
        type="button"
        className={cn(ghost, "flex items-center gap-[4px] text-ink")}
        onClick={t.onPickView}
      >
        {t.view}
        <ChevronDown aria-hidden className="size-[12px]" />
      </button>
      {t.savedViews?.map((name) => (
        <button
          key={name}
          type="button"
          className={ghost}
          onClick={() => {
            t.onSavedView?.(name);
          }}
        >
          {name}
        </button>
      ))}
      <button type="button" className={ghost} onClick={t.onAddView}>
        + View
      </button>
      <button
        type="button"
        data-filter-count={t.filters}
        className={cn(ghost, t.filters > 0 && "bg-amber-tint text-amber-ink")}
        onClick={t.onFilter}
      >
        {`Filter · ${String(t.filters)}`}
      </button>
      {t.filters > 0 && (
        <button type="button" className={ghost} onClick={t.onClearFilters}>
          Clear
        </button>
      )}
      <button type="button" className={ghost} onClick={t.onColumns}>
        Columns
      </button>
      <SearchField
        label="Search rows"
        value={t.search}
        onChange={t.onSearch}
        className="w-[200px]"
      />
      <span className="ml-auto flex items-center gap-[6px]">
        <button
          type="button"
          className={cn(ghost, "flex items-center gap-[4px]")}
          onClick={t.onSignOffs}
        >
          Sign-offs
          <ChevronDown aria-hidden className="size-[12px]" />
        </button>
        <button type="button" className={ghost} onClick={t.onAgents}>
          Agents
        </button>
        <button type="button" className={ghost} onClick={t.onComments}>
          Comments
        </button>
      </span>
    </div>
  );
}

export function SheetLayout({
  variant,
  view,
  toolbar,
  grid,
  signOffs,
  onOpenSignOff,
  presence,
  drawer,
  dock,
  onAddRow,
}: SheetLayoutProps): JSX.Element {
  const shown: SheetGridProps = {
    ...grid,
    rows: view === "ready" ? grid.rows : [],
    sections: view === "ready" ? grid.sections : [],
    trailing: {
      label: "P · R",
      width: PR_W,
      render: (row) => (
        <SignOffCell row={row} signed={signOffs?.[row.key]} onOpenSignOff={onOpenSignOff} />
      ),
    },
  };
  const body = (
    <div className="flex min-w-0 flex-col">
      <SheetGrid {...shown} />
      {view === "loading" && <SkeletonRows type="table" count={8} immediate />}
      {view === "empty" && (
        <EmptyState
          title={SHEET_EMPTY.title}
          action={
            <Button variant="secondary" size="sm" onClick={onAddRow}>
              {SHEET_EMPTY.action}
            </Button>
          }
        >
          {SHEET_EMPTY.body}
        </EmptyState>
      )}
    </div>
  );
  return (
    <div data-sheet-layout={variant} className="flex min-h-0 flex-col bg-card">
      <div className="flex items-center">
        <div className="min-w-0 flex-1">
          <Toolbar toolbar={toolbar} />
        </div>
        {presence !== undefined && (
          <div
            data-presence=""
            className="flex h-[44px] items-center border-b border-hair px-[10px]"
          >
            {presence}
          </div>
        )}
      </div>
      {variant === "cockpit" ? (
        <div className="flex min-h-0">
          <div
            data-canvas=""
            style={{ width: CANVAS_COCKPIT, maxWidth: CANVAS_COCKPIT }}
            className="shrink-0 overflow-x-auto"
          >
            {body}
          </div>
          {dock !== undefined && <div className="min-w-0 flex-1 border-l border-hair">{dock}</div>}
        </div>
      ) : (
        body
      )}
      {drawer !== undefined && (
        <Drawer
          open
          width={DRAWER_W}
          title={drawer.title}
          onOpenChange={(open) => {
            if (!open) drawer.onClose();
          }}
        >
          <UnderlineTabs
            label="Row"
            options={ROW_DRAWER_TABS}
            active={drawer.tab}
            onChange={(tab) => {
              drawer.onTab(tab as RowDrawerTab);
            }}
          />
          <div data-drawer-tab={drawer.tab} className="pt-[10px]">
            {drawer.slots[drawer.tab]}
          </div>
        </Drawer>
      )}
    </div>
  );
}
