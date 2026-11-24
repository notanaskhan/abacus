// BoardLayout T19 (F-08-T22; TASK-8928; F-08 §B2, §B3; handoff T19 a–l; ADR P-49; INV-1;
// DEC-5930): the board over statuses that already exist. The 44 toolbar: the view switch (Board ·
// Binder · Sheet), the filter buttons (an active one becomes the amber split chip, with Clear),
// "Search programs", and "Run agent on move" bound to the host's AI policy (disabled with Info and
// "Not allowed for this engagement type by AI policy" when the policy forbids it; off by default;
// never sends `runAgent: true` unless allowed and on). The body: the 280 navigator (the control
// set collapses it to the 44 rail), sticky 40 column headers with the server's counts (they sum to
// the record's tiles), then a 34 lane band per area with its cards under it, each lane a
// BoardCanvas (C-24 cards, dnd-kit, guarded moves, INV-1). Binder view is the tree table (folder
// rows per area: Name · To-dos · Preparer sign-offs · Reviewer sign-offs · Status); Sheet view is
// the host's T18. Empty is the designed EmptyState; loading keeps the headers real and pulses six
// skeleton cards. Variants: audit (4 × 262), control (6 × 196), returns, close.
import { type JSX, type ReactNode, useState } from "react";
import { cn } from "../cn";
import { FilterChip, type PickerOption, SearchField } from "../components/inputs";
import { Tooltip } from "../components/popover";
import { EmptyState, Skeleton } from "../components/states";
import { Segmented } from "../components/tabs";
import { Toggle } from "../components/toggles";
import type { SignOffSlot } from "../gates/sign-off-slots";
import { Icon } from "../icons";
import { BoardCanvas } from "./BoardCanvas";
import {
  BoardCard,
  type BoardCardProps,
  BoardColumnHeader,
  type BoardColumnHeaderProps,
  BoardLane,
  BoardNavigator,
  type NavigatorItem,
} from "./BoardCard";
import type { MoveIntent, MoveResult } from "./types";

export type BoardVariant = "audit" | "control" | "returns" | "close";
export type BoardView = "board" | "binder" | "sheet";

export const RUN_ON_MOVE_DENIED = "Not allowed for this engagement type by AI policy";

export interface BoardLayoutColumn {
  key: string;
  label: string;
  count: number;
  disc?: BoardColumnHeaderProps["disc"];
  accepts?: boolean;
}

export interface BoardLayoutLane {
  key: string;
  title: string;
  /** "2 programs". */
  meta?: string;
  /** "8 of 8" once every card in the lane is done. */
  done?: string;
  collapsed?: boolean;
}

export interface BoardLayoutCard extends Omit<BoardCardProps, "width" | "onOpen"> {
  id: string;
  lane: string;
  column: string;
  version: number;
  /** Binder view's columns: to-dos done ("2 of 3") and the status word. */
  todos?: string;
  status?: string;
}

export interface BoardFilter {
  key: string;
  label: string;
  icon?: "atom" | "layers" | "folder-tree" | "user";
  options: readonly PickerOption[];
  value: string | null;
}

export interface BoardLayoutProps {
  variant: BoardVariant;
  label: string;
  view: BoardView;
  onView?: (view: BoardView) => void;
  columns: readonly BoardLayoutColumn[];
  lanes: readonly BoardLayoutLane[];
  cards: readonly BoardLayoutCard[];
  filters?: readonly BoardFilter[];
  onFilter?: (key: string, value: string | null) => void;
  onClearFilters?: () => void;
  search?: string;
  searchLabel?: string;
  onSearch?: (q: string) => void;
  /** The host's AI policy (ADR P-49) and the toggle's state; the tooltip when allowed. */
  runOnMove: { allowed: boolean; on: boolean; allowedTip?: string };
  onRunOnMove?: (on: boolean) => void;
  navigator?: { title: string; items: readonly NavigatorItem[]; collapsed?: boolean };
  state?: "ready" | "loading" | "empty";
  empty?: { title: string; body: string };
  onMoveIntent: (intent: MoveIntent) => Promise<MoveResult>;
  onOpenSignOff?: (cardId: string) => void;
  onOpenCard?: (cardId: string) => void;
  /** Sheet view: the host's T18 over the same rows. */
  sheet?: ReactNode;
  /** Specimens: hold a drag (T19b). */
  forceDrag?: { cardId: string; over: string } | undefined;
}

const VIEWS: readonly { v: BoardView; label: string; icon: "kanban" | "folder-tree" | "table" }[] =
  [
    { v: "board", label: "Board", icon: "kanban" },
    { v: "binder", label: "Binder", icon: "folder-tree" },
    { v: "sheet", label: "Sheet", icon: "table" },
  ];

function slotText(slot: SignOffSlot | undefined): string {
  if (!slot?.signer) return "—";
  return slot.stale ? `${slot.signer} · changed since` : slot.signer;
}

function Binder({
  lanes,
  cards,
}: {
  lanes: readonly BoardLayoutLane[];
  cards: readonly BoardLayoutCard[];
}): JSX.Element {
  const heads = ["Name", "To-dos", "Preparer sign-offs", "Reviewer sign-offs", "Status"];
  return (
    <table className="w-full border-collapse bg-card text-[13px]" data-board-binder="">
      <thead>
        <tr className="hairline-b">
          {heads.map((h) => (
            <th
              key={h}
              scope="col"
              className="h-[30px] bg-nested px-[10px] text-left text-[12px] font-normal text-ink-2"
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {lanes.map((lane) => (
          <BinderLane
            key={lane.key}
            lane={lane}
            cards={cards.filter((c) => c.lane === lane.key)}
          />
        ))}
      </tbody>
    </table>
  );
}

function BinderLane({
  lane,
  cards,
}: {
  lane: BoardLayoutLane;
  cards: readonly BoardLayoutCard[];
}) {
  return (
    <>
      <tr className="h-[34px] bg-band-hd hairline-b" data-binder-folder={lane.key}>
        <td colSpan={5} className="px-[10px] font-medium">
          <span className="inline-flex items-center gap-[6px]">
            <Icon name="folder" size={14} className="text-ink-3" />
            {lane.title}
            {lane.meta ? <span className="font-normal text-ink-3">{`· ${lane.meta}`}</span> : null}
          </span>
        </td>
      </tr>
      {cards.map((c) => (
        <tr key={c.id} className="h-[36px] hairline-b" data-binder-row={c.id}>
          <td className="pl-[34px] pr-[10px]">
            <span className="font-mono text-[11px] text-ink-3">{c.code}</span> {c.title}
          </td>
          <td className="px-[10px] tabular-nums">{c.todos ?? "—"}</td>
          <td className="px-[10px]">{slotText(c.p)}</td>
          <td className="px-[10px]">{slotText(c.r)}</td>
          <td className="px-[10px]">{c.status ?? "—"}</td>
        </tr>
      ))}
    </>
  );
}

/** The C-24 props of a layout card (its lane, column, version and binder words are the layout's). */
function cardProps(card: BoardLayoutCard): Omit<BoardCardProps, "width" | "onOpen"> {
  const skip: ReadonlySet<string> = new Set([
    "id",
    "lane",
    "column",
    "version",
    "todos",
    "status",
  ]);
  return Object.fromEntries(Object.entries(card).filter(([k]) => !skip.has(k))) as Omit<
    BoardCardProps,
    "width" | "onOpen"
  >;
}

export function BoardLayout(p: BoardLayoutProps): JSX.Element {
  const compact = p.variant === "control";
  const width: 262 | 196 = compact ? 196 : 262;
  const [collapsedLanes, setCollapsedLanes] = useState<ReadonlySet<string>>(
    () => new Set(p.lanes.filter((l) => l.collapsed === true).map((l) => l.key)),
  );
  const [navCollapsed, setNavCollapsed] = useState(p.navigator?.collapsed ?? compact);
  const active = (p.filters ?? []).filter((f) => f.value !== null);
  const filtered = active.length > 0 || (p.search ?? "") !== "";
  const visibleLanes = filtered
    ? p.lanes.filter((l) => p.cards.some((c) => c.lane === l.key))
    : p.lanes;
  const state = p.state ?? "ready";
  const toggle = (
    <Toggle
      checked={p.runOnMove.allowed && p.runOnMove.on}
      disabled={!p.runOnMove.allowed}
      label="Run agent on move"
      onChange={(on) => p.onRunOnMove?.(on)}
    />
  );
  return (
    <div data-board-layout={p.variant} data-view={p.view} className="flex min-h-0 flex-1 flex-col">
      <div
        className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]"
        data-board-toolbar=""
      >
        <Segmented
          size="small"
          label="View"
          options={VIEWS.map((v) => ({ label: v.label, icon: v.icon }))}
          active={VIEWS.find((v) => v.v === p.view)?.label ?? "Board"}
          onChange={(label) => p.onView?.(VIEWS.find((v) => v.label === label)?.v ?? "board")}
        />
        <span aria-hidden className="h-[18px] w-[0.5px] bg-hair" />
        {(p.filters ?? []).map((f) => (
          <FilterChip
            key={f.key}
            label={f.label}
            {...(f.icon ? { icon: f.icon } : {})}
            options={f.options}
            value={f.value}
            onChange={(v) => p.onFilter?.(f.key, v)}
          />
        ))}
        {filtered ? (
          <button
            type="button"
            onClick={p.onClearFilters}
            className="text-[12.5px] font-medium text-ink underline-offset-2 hover:underline"
          >
            Clear
          </button>
        ) : null}
        <span className="w-[200px]">
          <SearchField
            label={p.searchLabel ?? "Search programs"}
            value={p.search ?? ""}
            onChange={(q) => p.onSearch?.(q)}
          />
        </span>
        <span className="flex-1" />
        <span
          className="flex items-center gap-[8px] text-[13px] text-ink-2"
          data-run-on-move={p.runOnMove.allowed ? "allowed" : "denied"}
        >
          Run agent on move
          {p.runOnMove.allowed ? (
            p.runOnMove.allowedTip ? (
              <Tooltip content={p.runOnMove.allowedTip}>{toggle}</Tooltip>
            ) : (
              toggle
            )
          ) : (
            <Tooltip content={RUN_ON_MOVE_DENIED}>
              <span className="inline-flex items-center gap-[4px]">
                {toggle}
                <Icon name="info" size={12} className="text-ink-3" />
              </span>
            </Tooltip>
          )}
        </span>
        <span aria-label="More" className="px-[6px] text-ink-3">
          ···
        </span>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px] pt-[10px]">
        {p.navigator && p.view === "board" ? (
          <BoardNavigator
            title={p.navigator.title}
            items={p.navigator.items}
            collapsed={navCollapsed}
            onToggle={setNavCollapsed}
          />
        ) : null}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto">
          {p.view === "sheet" ? (
            <div data-board-sheet="">{p.sheet}</div>
          ) : p.view === "binder" ? (
            <Binder lanes={visibleLanes} cards={p.cards} />
          ) : state === "empty" ? (
            <EmptyState icon="kanban" title={p.empty?.title ?? "No programs yet."}>
              {p.empty?.body ?? "Programs appear when the engagement template is applied."}
            </EmptyState>
          ) : (
            <>
              <div
                role="row"
                className={cn(
                  "sticky top-0 z-10 flex px-[8px]",
                  compact ? "gap-[8px]" : "gap-[10px]",
                )}
              >
                {p.columns.map((c) => (
                  <span key={c.key} style={{ width: width + 16 }} className="flex-none px-[8px]">
                    <BoardColumnHeader
                      label={c.label}
                      count={c.count}
                      {...(c.disc ? { disc: c.disc } : {})}
                      width="100%"
                    />
                  </span>
                ))}
              </div>
              {state === "loading" ? (
                <div
                  className="grid gap-[10px] p-[16px]"
                  data-board-loading=""
                  style={{
                    gridTemplateColumns: `repeat(${String(p.columns.length)}, ${String(width)}px)`,
                  }}
                >
                  {Array.from({ length: 6 }, (_, i) => (
                    <Skeleton key={i} className="h-[112px] rounded-[10px]" />
                  ))}
                </div>
              ) : (
                visibleLanes.map((lane) => {
                  const mine = p.cards.filter((c) => c.lane === lane.key);
                  const collapsed = collapsedLanes.has(lane.key);
                  return (
                    <BoardLane
                      key={lane.key}
                      title={lane.title}
                      {...(lane.meta ? { meta: lane.meta } : {})}
                      {...(lane.done && collapsed ? { done: lane.done } : {})}
                      collapsed={collapsed}
                      onToggle={(c) => {
                        setCollapsedLanes((s) => {
                          const next = new Set(s);
                          if (c) next.add(lane.key);
                          else next.delete(lane.key);
                          return next;
                        });
                      }}
                    >
                      <BoardCanvas
                        label={lane.title}
                        columns={p.columns.map((c) => ({
                          key: c.key,
                          label: c.label,
                          count: c.count,
                          ...(c.accepts === undefined ? {} : { accepts: c.accepts }),
                        }))}
                        cards={mine.map((c) => ({
                          id: c.id,
                          column: c.column,
                          title: c.title,
                          version: c.version,
                        }))}
                        onMoveIntent={p.onMoveIntent}
                        {...(p.onOpenSignOff ? { onOpenSignOff: p.onOpenSignOff } : {})}
                        runOnMove={{ allowed: p.runOnMove.allowed, on: p.runOnMove.on }}
                        columnWidth={width}
                        headers={false}
                        bareCards
                        forceDrag={
                          p.forceDrag && mine.some((c) => c.id === p.forceDrag?.cardId)
                            ? p.forceDrag
                            : undefined
                        }
                        renderCard={(vm) => {
                          const card = mine.find((c) => c.id === vm.id);
                          if (card === undefined) return null;
                          return (
                            <BoardCard
                              {...cardProps(card)}
                              width={width}
                              {...(p.onOpenCard ? { onOpen: () => p.onOpenCard?.(card.id) } : {})}
                            />
                          );
                        }}
                      />
                    </BoardLane>
                  );
                })
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
