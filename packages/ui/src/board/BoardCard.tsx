// BoardCard C-24, its column Header and Lane, C-26 AgentProgress and the 280 BoardNavigator
// (F-08-T21; TASK-8927; F-08 §B3; T19 a–l; handoff kits BoardCard, AgentProgress, SignOff;
// DEC-5929). Read-model parts: every count, metric and state is the host's; the card computes
// nothing and holds no action that signs off, approves, releases, sends or posts (INV-1).
//
// - Card (262 or 196 wide, radius 10, e1; hover e2; selected an inset ring; ghost e3 rotated
//   1.5°): title (two lines), the owner chip (20 px, never larger), ID, the four metrics (days ·
//   evidence · requests · to-dos), C-26 AgentProgress and the C-25 P/R slots. Variants: program
//   (audit), control (ID + owner, TSC tag, test result), return (sub-line, pill, due) and close
//   (to-dos done count).
// - Overlays, distinct without any colour fill on the card: Needs input (an amber dot and words),
//   Waiting on client (a muted pill), Agent running (the ink-2 spinner by the title), Sent back
//   (a 3 px brick bar on the left edge and "Sent back · <who>").
// - Header (40, sticky): StatusDisc, label and the server's Count.
// - Lane (34, band): chevron, area title, "· meta", and the DoneCount when every card is done.
// - Navigator (280): phases and areas with counts; collapses to a 44 rail.
import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Pill } from "../components/pill";
import { StatusDisc } from "../components/status";
import type { DiscState } from "../status";
import type { SignOffSlot } from "../gates/sign-off-slots";
import { Icon, type IconName } from "../icons";
import { Spinner } from "../components/motion";

// ---- C-26 AgentProgress ------------------------------------------------------------------------

export type AgentProgressState =
  "progress" | "running" | "input" | "client" | "done" | "not_run" | "none";

export interface AgentProgressProps {
  state: AgentProgressState;
  /** The run's percent (0–100), the server's: the bar for "progress", and beside "Running". */
  pct?: number;
  /** The run's line ("Procedure session · BH-FS-430 · Cole Hart via Agent · started 10:05 AM"). */
  tip?: string;
  /** Opens the run (SHL-13); a read, never a decision. */
  onOpen?: () => void;
}

function Bar({ pct }: { pct: number }): JSX.Element {
  const width = Math.max(0, Math.min(100, pct));
  return (
    <span className="flex items-center gap-[6px]" data-agent-progress={width}>
      <span className="h-[3px] w-[96px] overflow-hidden rounded-pill bg-chip">
        <span
          className="block h-full rounded-pill bg-ink"
          style={{ width: `${String(width)}%` }}
        />
      </span>
      <span className="text-[11px] tabular-nums text-ink-2">{`${String(width)}%`}</span>
    </span>
  );
}

/** C-26: the Accrued Agent's state on a card: a bar with its percent, a chip, or "Not run". */
export function AgentProgress({
  state,
  pct,
  tip,
  onOpen,
}: AgentProgressProps): JSX.Element | null {
  if (state === "none") return null;
  if (state === "not_run") {
    return (
      <span
        data-agent="not_run"
        className="inline-flex items-center gap-[6px] text-[11px] text-ink-4"
      >
        <Icon name="atom" size={12} />
        Not run
      </span>
    );
  }
  const chip =
    state === "progress" ? null : (
      <span
        className={cn(
          "flex items-center gap-[4px] text-[11px]",
          state === "done" ? "font-medium text-green-ink" : "text-ink-2",
        )}
      >
        {state === "running" ? <Spinner size={10} label="Running" /> : null}
        {state === "input" ? (
          <span aria-hidden className="size-[6px] rounded-full bg-amber" />
        ) : null}
        {state === "done" ? <StatusDisc state="done" size={13} /> : null}
        {
          { running: "Running", input: "Needs input", client: "Waiting on client", done: "Done" }[
            state
          ]
        }
      </span>
    );
  return (
    <button
      type="button"
      onClick={onOpen}
      title={tip}
      data-agent={state}
      className="inline-flex items-center gap-[6px] text-[11px] text-ink-2"
    >
      <Icon name="atom" size={12} className="text-ink-3" />
      {chip}
      {state === "progress" || (state === "running" && pct !== undefined) ? (
        <Bar pct={pct ?? 0} />
      ) : null}
    </button>
  );
}

// ---- C-25 P/R slots on a card --------------------------------------------------------------------

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w.charAt(0))
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

/** C-25 on a card: a signed slot is the olive-dot initials chip, a stale one the amber "!",
 * an empty one a ring with its letter. */
function Slot({ slot, letter }: { slot: SignOffSlot | undefined; letter: string }): JSX.Element {
  const signed = slot?.signer !== null && slot?.signer !== undefined;
  const stale = slot?.stale === true;
  const label = slot
    ? signed
      ? `${slot.role}: ${slot.signer ?? ""}${slot.at ? ` · ${slot.at}` : ""}${stale ? " · changed since" : ""}`
      : `${slot.role}: not signed`
    : `${letter}: not signed`;
  const state = stale ? "stale" : signed ? "signed" : "empty";
  if (signed && !stale) {
    return (
      <span
        title={label}
        aria-label={label}
        data-slot={state}
        className="inline-flex h-[18px] items-center gap-[4px] rounded-pill bg-green-tint px-[6px] text-[10.5px] font-medium text-green-ink"
      >
        <span aria-hidden className="size-[4px] rounded-full bg-green" />
        {initials(slot.signer ?? "")}
      </span>
    );
  }
  return (
    <span
      title={label}
      aria-label={label}
      data-slot={state}
      className={cn(
        "inline-flex size-[18px] items-center justify-center rounded-full text-[9.5px] font-medium",
        stale ? "text-amber-ink ring-1 ring-amber" : "text-ink-4 ring-1 ring-ink-4",
      )}
    >
      {stale ? "!" : letter}
    </span>
  );
}

// ---- C-24 BoardCard -----------------------------------------------------------------------------

export type BoardCardVariant = "program" | "control" | "return" | "close";
export type BoardCardLook = "rest" | "hover" | "selected" | "ghost";

export interface BoardCardProps {
  variant?: BoardCardVariant;
  title: string;
  /** "BH-FS-430". */
  code: string;
  /** The owner's initials ("CH") and name for the chip's title. */
  owner: string;
  ownerName: string;
  look?: BoardCardLook;
  /** Overlays: Needs input, Waiting on client. */
  flag?: "" | "input" | "client";
  /** The Accrued Agent is running on this card (the spinner by the title). */
  spin?: boolean;
  /** Sent back by a reviewer: the brick bar and "Sent back · <name>". */
  sentBy?: string;
  /** [days open, evidence, requests, to-dos], the server's. */
  metrics?: readonly [number, number, number, number];
  agent?: AgentProgressProps;
  p?: SignOffSlot;
  r?: SignOffSlot;
  width?: 262 | 196 | "100%";
  /** control: the TSC tag and the test result. */
  tag?: string;
  result?: "none" | "exc";
  /** return and program: a sub-line. */
  sub?: string;
  /** return: the status pill and the due line. */
  pill?: string;
  due?: string;
  /** close: the to-dos done count ("3 of 5"). */
  done?: { text: string; complete?: boolean; running?: boolean };
  onOpen?: (code: string) => void;
}

const METRICS: readonly { icon: IconName; tip: string }[] = [
  { icon: "calendar", tip: "Days open" },
  { icon: "paperclip", tip: "Evidence" },
  { icon: "inbox", tip: "Requests" },
  { icon: "list-checks", tip: "To-dos" },
];

function Owner({ owner, ownerName }: { owner: string; ownerName: string }): JSX.Element {
  return (
    <span
      title={ownerName}
      data-owner=""
      className="inline-flex size-[20px] flex-none items-center justify-center rounded-full bg-chip text-[10.5px] font-medium text-ink-2"
    >
      {owner}
    </span>
  );
}

export function BoardCard(p: BoardCardProps): JSX.Element {
  const variant = p.variant ?? "program";
  const look = p.look ?? "rest";
  const width = p.width ?? 262;
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${p.code} ${p.title}`}
      data-card={p.code}
      data-look={look}
      data-flag={p.flag || undefined}
      {...(p.sentBy ? { "data-sent-back": "" } : {})}
      onClick={() => p.onOpen?.(p.code)}
      onKeyDown={(e) => {
        if (e.key === "Enter") p.onOpen?.(p.code);
      }}
      style={{ width: width === "100%" ? "100%" : width }}
      className={cn(
        "relative flex flex-col gap-[6px] overflow-hidden rounded-[10px] bg-card px-[12px] py-[10px] shadow-e1 outline-none",
        look === "hover" && "shadow-e2",
        look === "selected" && "ring-2 ring-inset ring-ink",
        look === "ghost" && "rotate-[1.5deg] shadow-e3",
      )}
    >
      {p.sentBy ? (
        <span
          aria-hidden
          data-bar="sent-back"
          className="absolute inset-y-0 left-0 w-[3px] bg-red"
        />
      ) : null}
      {p.flag === "input" ? (
        <span className="inline-flex items-center gap-[6px] text-[11.5px] text-amber-ink">
          <span aria-hidden className="size-[8px] flex-none rounded-full bg-amber" />
          Needs input
        </span>
      ) : null}
      {p.flag === "client" ? (
        <span className="self-start">
          <Pill variant="muted" size="sm">
            Waiting on client
          </Pill>
        </span>
      ) : null}
      {variant === "control" ? (
        <>
          <div className="flex items-center gap-[8px]">
            <span className="min-w-0 flex-1 font-mono text-[11px] text-ink-3">{p.code}</span>
            <Owner owner={p.owner} ownerName={p.ownerName} />
          </div>
          <span className="line-clamp-2 text-[13px] font-medium leading-[1.3]">{p.title}</span>
          <div className="flex flex-wrap items-center gap-[6px]">
            {p.tag ? (
              <Pill variant="outline" size="sm" title="Trust Services Criteria">
                {p.tag}
              </Pill>
            ) : null}
            {p.result === "exc" ? (
              <Pill variant="red-tint" size="sm">
                Exceptions noted
              </Pill>
            ) : (
              <Pill variant="neutral" size="sm">
                Not tested
              </Pill>
            )}
          </div>
        </>
      ) : (
        <div className="flex items-start gap-[8px]">
          <span className="line-clamp-2 min-w-0 flex-1 text-[13px] font-medium leading-[1.3]">
            {p.title}
          </span>
          {p.spin ? (
            <span
              title="Accrued Agent is running"
              data-spin=""
              className="mt-[4px] flex-none text-ink-2"
            >
              <Spinner size={12} label="Accrued Agent is running" />
            </span>
          ) : null}
          <Owner owner={p.owner} ownerName={p.ownerName} />
        </div>
      )}
      {variant === "program" ? (
        <>
          <div className="flex flex-col gap-[3px]">
            <span className="font-mono text-[11px] text-ink-3">{p.code}</span>
            {p.sentBy ? (
              <span className="text-[11px] text-ink-3">{`Sent back · ${p.sentBy}`}</span>
            ) : null}
            {p.sub ? <span className="text-[11.5px] text-ink-2">{p.sub}</span> : null}
          </div>
          {p.metrics ? (
            <div className="flex items-center gap-[10px] text-[11.5px] text-ink-3" data-metrics="">
              {METRICS.map((m, i) => (
                <span key={m.tip} title={m.tip} className="inline-flex items-center gap-[4px]">
                  <Icon name={m.icon} size={12} />
                  <span className="tabular-nums">{p.metrics?.[i] ?? 0}</span>
                </span>
              ))}
            </div>
          ) : null}
          <div className="flex items-center justify-between gap-[8px]">
            <span className="flex min-w-0 flex-1">
              {p.agent ? <AgentProgress {...p.agent} /> : null}
            </span>
            <span className="flex flex-none gap-[3px]" data-slots="">
              <Slot slot={p.p} letter="P" />
              <Slot slot={p.r} letter="R" />
            </span>
          </div>
        </>
      ) : null}
      {variant === "return" ? (
        <>
          {p.sub ? <span className="text-[11.5px] text-ink-3">{p.sub}</span> : null}
          <div className="flex items-center gap-[8px]">
            {p.pill ? (
              <Pill variant="amber" size="sm">
                {p.pill}
              </Pill>
            ) : null}
            <span className="flex-1" />
            {p.due ? <span className="text-[11.5px] text-ink-3">{p.due}</span> : null}
          </div>
        </>
      ) : null}
      {variant === "close" && p.done ? (
        <div className="flex items-center gap-[8px]">
          <Pill variant={p.done.complete ? "green-tint" : "neutral"} size="sm" data-done="">
            {p.done.running ? <Spinner size={10} label="Running" /> : null}
            {p.done.text}
            {p.done.complete ? <Icon name="check" size={12} /> : null}
          </Pill>
          <span className="text-[11.5px] text-ink-3">to-dos done</span>
        </div>
      ) : null}
    </div>
  );
}

// ---- Header and Lane ----------------------------------------------------------------------------

export interface BoardColumnHeaderProps {
  label: string;
  /** The server's count (the columns sum to the record's tiles). */
  count: number;
  /** todo · half · running · muted · dot · done. */
  disc?: "todo" | "half" | "running" | "muted" | "dot" | "done";
  width?: 262 | 196 | "100%";
}

const DISC: Partial<Record<NonNullable<BoardColumnHeaderProps["disc"]>, DiscState>> = {
  todo: "todo",
  half: "half",
  running: "run",
  done: "done",
};

export function BoardColumnHeader({
  label,
  count,
  disc = "todo",
  width = 262,
}: BoardColumnHeaderProps): JSX.Element {
  const state = DISC[disc];
  return (
    <div
      role="columnheader"
      data-column-header={label}
      style={{ width: width === "100%" ? "100%" : width }}
      className="sticky top-0 z-10 flex h-[40px] items-center gap-[8px] rounded-[10px] bg-card px-[12px] shadow-e1"
    >
      <span className="flex size-[15px] flex-none items-center justify-center">
        {state ? <StatusDisc state={state} size={15} /> : null}
        {disc === "muted" ? (
          <span title="Pending" className="size-[15px] rounded-full bg-chip" />
        ) : null}
        {disc === "dot" ? <span className="size-[8px] rounded-full bg-amber" /> : null}
      </span>
      <span className="min-w-0 truncate text-[13.5px] font-medium">{label}</span>
      <span
        data-count=""
        className="inline-flex h-[19px] min-w-[19px] flex-none items-center justify-center rounded-pill bg-chip px-[6px] text-[11.5px] font-medium tabular-nums text-ink-2"
      >
        {count}
      </span>
    </div>
  );
}

export interface BoardLaneProps {
  title: string;
  /** "· 3 programs". */
  meta?: string;
  /** "8 of 8" when every card in the lane is done (the DoneCount, green-tint with a check). */
  done?: string;
  collapsed: boolean;
  onToggle?: (collapsed: boolean) => void;
  children?: ReactNode;
}

export function BoardLane({
  title,
  meta,
  done,
  collapsed,
  onToggle,
  children,
}: BoardLaneProps): JSX.Element {
  return (
    <section aria-label={title} data-lane={title}>
      <button
        type="button"
        aria-expanded={!collapsed}
        onClick={() => onToggle?.(!collapsed)}
        className="flex h-[34px] w-full items-center gap-[6px] border-y-[0.5px] border-hair bg-band-hd px-[12px] text-left hover:bg-nav-fill"
      >
        <Icon
          name={collapsed ? "chevron-right" : "chevron-down"}
          size={12}
          className="text-ink-3"
        />
        <span className="whitespace-nowrap text-[13.5px] font-medium">{title}</span>
        {meta ? (
          <span className="whitespace-nowrap text-[13.5px] text-ink-3">{`· ${meta}`}</span>
        ) : null}
        {done ? (
          <span
            data-lane-done=""
            className="ml-[2px] inline-flex h-[19px] items-center gap-[4px] rounded-pill bg-green-tint px-[7px] text-[11.5px] font-medium tabular-nums text-green-ink"
          >
            {done}
            <Icon name="check" size={12} />
          </span>
        ) : null}
      </button>
      {collapsed ? null : children}
    </section>
  );
}

// ---- Navigator ----------------------------------------------------------------------------------

export interface NavigatorItem {
  key: string;
  label: string;
  count: number;
  /** An area under a phase. */
  depth?: 0 | 1;
}

export interface BoardNavigatorProps {
  title: string;
  items: readonly NavigatorItem[];
  /** The 44 rail (T19h) instead of the 280 navigator. */
  collapsed: boolean;
  onToggle?: (collapsed: boolean) => void;
  selected?: string;
  onSelect?: (key: string) => void;
}

/** The 280 navigator (phases and areas with counts); collapses to a 44 rail. */
export function BoardNavigator({
  title,
  items,
  collapsed,
  onToggle,
  selected,
  onSelect,
}: BoardNavigatorProps): JSX.Element {
  if (collapsed) {
    return (
      <nav
        aria-label={title}
        data-navigator="rail"
        className="flex w-[44px] flex-none flex-col items-center gap-[8px] bg-card py-[10px] shadow-e1"
      >
        <button
          type="button"
          aria-label={`Open ${title}`}
          onClick={() => onToggle?.(false)}
          className="text-ink-2"
        >
          <Icon name="panel-left-open" size={16} />
        </button>
      </nav>
    );
  }
  return (
    <nav
      aria-label={title}
      data-navigator="open"
      className="flex w-[280px] flex-none flex-col bg-card shadow-e1"
    >
      <header className="flex h-[40px] items-center gap-[8px] px-[12px] hairline-b">
        <span className="flex-1 text-[13.5px] font-medium">{title}</span>
        <button
          type="button"
          aria-label={`Collapse ${title}`}
          onClick={() => onToggle?.(true)}
          className="text-ink-2"
        >
          <Icon name="panel-left-close" size={16} />
        </button>
      </header>
      <ul className="flex flex-col py-[4px]">
        {items.map((it) => (
          <li key={it.key}>
            <button
              type="button"
              aria-current={selected === it.key ? "true" : undefined}
              onClick={() => onSelect?.(it.key)}
              className={cn(
                "flex h-[30px] w-full items-center gap-[8px] text-left text-[13px]",
                it.depth === 1 ? "pl-[28px] pr-[12px] text-ink-2" : "px-[12px] font-medium",
                selected === it.key && "bg-nested",
              )}
            >
              <span className="min-w-0 flex-1 truncate">{it.label}</span>
              <span className="text-[11.5px] tabular-nums text-ink-3">{it.count}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
