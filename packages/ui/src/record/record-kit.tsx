import type { JSX } from "react";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { Pill } from "../components/pill";
import { Menu } from "../components/popover";
import { StatusDisc } from "../components/status";
import { type ForceState, forceAttr } from "../force-state";
import { Icon, type IconName } from "../icons";
import type { PillVariant } from "../status";
import type { KvGroup, KvRow, RecordKind, RecordStat, RecordTone } from "./types";

// The C-04 Record kit (F-05-T40): the recessed OverviewCard at the top of the 330 rail, the
// AboutCard, and the close Summary parts (StatusDropdownPill, StatRows, a GroupBand and KVRows).
// Words plus colour, never colour alone: every tone is a pill with its word.

/** The icon tile per record kind (espresso only, never coloured). */
export const KIND_ICON: Record<RecordKind, IconName> = {
  audit: "file-text",
  tax: "receipt",
  close: "book-open",
};

const STATE_TONE: Readonly<Record<string, RecordTone>> = {
  "Not started": "neutral",
  Archived: "neutral",
  Ready: "ready",
  Approved: "ready",
  Issued: "done",
  Filed: "done",
  Accepted: "done",
  Closed: "done",
  Complete: "done",
  Delivered: "done",
  Rejected: "issue",
  "Waiting on inputs": "muted",
  Pending: "muted",
};

/** A record state's tone (A7): anything not listed is in flight, so amber. */
export function recordTone(state: string): RecordTone {
  return STATE_TONE[state] ?? "amber";
}

const TONE_VARIANT: Record<RecordTone, PillVariant> = {
  amber: "amber",
  done: "green",
  ready: "green-tint",
  issue: "red-tint",
  neutral: "neutral",
  muted: "muted",
};

/** A record's state as the card's 21px pill, toned by `recordTone`. */
export function RecordStatePill({ state }: { state: string }): JSX.Element {
  const tone = recordTone(state);
  return (
    <Pill
      variant={TONE_VARIANT[tone]}
      size="card-state"
      check={tone === "done"}
      data-tone={tone}
      className={cn(tone === "neutral" && "text-ink")}
    >
      {state}
    </Pill>
  );
}

const RECESS = "rounded-pane bg-shell inset-shadow-hair";

function Tile({ icon, large = false }: { icon: IconName; large?: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex flex-none items-center justify-center bg-espresso text-on-dark shadow-cta",
        large ? "size-[44px] rounded-menu-inner" : "size-[34px] rounded-tile-lg",
      )}
    >
      <Icon name={icon} size={large ? 20 : 17} />
    </span>
  );
}

export interface OverviewCardProps {
  kind?: RecordKind;
  /** Overrides the kind's icon. */
  icon?: IconName;
  title: string;
  sub: string;
  /** The state pill ("Planning", "Processing", "Filed"); none when absent. */
  state?: string;
  className?: string;
}

/** The record's card at the top of the rail: recessed and centred, never raised or shadowed. */
export function OverviewCard({
  kind = "audit",
  icon,
  title,
  sub,
  state,
  className,
}: OverviewCardProps): JSX.Element {
  return (
    <div
      data-record="overview-card"
      className={cn(
        "m-[10px] flex flex-col items-center px-[12px] pt-[14px] pb-[13px] text-center",
        RECESS,
        className,
      )}
    >
      <Tile icon={icon ?? KIND_ICON[kind]} />
      <p className="mt-[9px] text-section leading-[1.25] font-medium text-balance">{title}</p>
      <p className="mt-[2px] text-meta text-ink-3">{sub}</p>
      {state !== undefined && state !== "" && (
        <span className="mt-[8px]">
          <RecordStatePill state={state} />
        </span>
      )}
    </div>
  );
}

export interface AboutCardProps {
  icon: IconName;
  title: string;
  body: string;
  className?: string;
}

/** The same recess with a 44px tile and a paragraph ("Agents follow written instructions..."). */
export function AboutCard({ icon, title, body, className }: AboutCardProps): JSX.Element {
  return (
    <div
      data-record="about-card"
      className={cn(
        "m-[10px] flex flex-col items-center px-[16px] py-[18px] text-center",
        RECESS,
        className,
      )}
    >
      <Tile icon={icon} large />
      <p className="mt-[11px] text-pane font-medium tracking-[-0.012em]">{title}</p>
      <p className="mt-[4px] max-w-[320px] text-para text-ink-2">{body}</p>
    </div>
  );
}

// ---- Summary parts ------------------------------------------------------------------------------

/** The close status transitions (C-04 `CLOSE_FLOW`): the dropdown offers only these. */
export const CLOSE_FLOW: Readonly<Record<string, readonly string[]>> = {
  "Not started": ["In progress"],
  "In progress": ["In review", "Not started"],
  "In review": ["Closed", "In progress"],
  Closed: ["In progress"],
};

export interface StatusDropdownPillProps {
  status: string;
  /** The allowed moves from each status; default `CLOSE_FLOW`. */
  transitions?: Readonly<Record<string, readonly string[]>>;
  onStatus?: (next: string, prev: string) => void;
  forceState?: "open";
}

/** The 25px status pill that opens a menu of the allowed transitions only. */
export function StatusDropdownPill({
  status,
  transitions = CLOSE_FLOW,
  onStatus,
  forceState,
}: StatusDropdownPillProps): JSX.Element {
  const tone = recordTone(status);
  const next = transitions[status] ?? [];
  return (
    <Menu
      label="Change status"
      width={180}
      align="center"
      {...(forceState === undefined ? {} : { forceState })}
      disabled={next.length === 0}
      trigger={
        <button
          type="button"
          aria-label={`Status: ${status}`}
          className={cn("rounded-pill hover:brightness-[.97]", PRESS)}
        >
          <Pill
            variant={TONE_VARIANT[tone]}
            size="status"
            check={tone === "done"}
            className={cn(tone === "neutral" && "text-ink")}
          >
            {status}
          </Pill>
        </button>
      }
      sections={[
        next.map((label) => ({
          label,
          onSelect: () => {
            onStatus?.(label, status);
          },
        })),
      ]}
    />
  );
}

const LINK_ROW = "hover:bg-nested data-[force=hover]:bg-nested outline-offset-[-2px]";

export interface StatRowProps {
  stat: RecordStat;
  onOpen?: (stat: RecordStat) => void;
  forceState?: Extract<ForceState, "hover" | "focus">;
}

/** A stat row that is a link: a 15px tabular value over a 12px caption, then the chevron. */
export function StatRow({ stat, onOpen, forceState }: StatRowProps): JSX.Element {
  return (
    <button
      type="button"
      data-record="stat"
      {...forceAttr(forceState)}
      onClick={() => {
        onOpen?.(stat);
      }}
      className={cn(
        "flex w-full items-center gap-[8px] px-[12px] pt-[9px] pb-[10px] text-left hairline-b",
        LINK_ROW,
      )}
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-title font-normal tracking-[-0.012em] tabular-nums">
          {stat.value}
        </span>
        <span
          className={cn(
            "text-cell leading-[1.3]",
            stat.overdue === true ? "text-red-ink" : "text-ink-3",
          )}
        >
          {stat.caption}
        </span>
      </span>
      <Icon name="chevron-right" size={12} className="text-ink-3" />
    </button>
  );
}

/** The 31px band over a group of rows ("Details", "Review and Delivery"). */
export function RecordBand({ title }: { title: string }): JSX.Element {
  return (
    <div className="flex h-[31px] items-center bg-band-hd px-[12px] text-section font-medium hairline-b">
      {title}
    </div>
  );
}

export interface KvRowViewProps {
  row: KvRow;
  /** The default trail for link rows. */
  linkTrail?: "chevron" | "arrow";
  /** The person picker's options. */
  people?: readonly string[];
  onOpen?: (row: KvRow) => void;
  /** A different person was picked; that row's sign-off is cleared by the caller. */
  onAssign?: (row: KvRow, name: string) => void;
}

const KV =
  "flex min-h-[33px] w-full items-center gap-[8px] px-[12px] py-[5px] text-body hairline-b";

/** A key and its value: text, a link (ink, never clay) or a person picker. */
export function KvRowView({
  row,
  linkTrail = "chevron",
  people = [],
  onOpen,
  onAssign,
}: KvRowViewProps): JSX.Element {
  const kind = row.kind ?? "text";
  const key = (
    <span className="flex max-w-[55%] min-w-0 items-center gap-[8px] text-ink-2">
      {row.signed !== undefined && <StatusDisc state={row.signed ? "done" : "todo"} />}
      <span className="truncate">{row.label}</span>
    </span>
  );
  if (kind === "link") {
    const trail = row.trail ?? linkTrail;
    return (
      <button
        type="button"
        data-record="kv"
        data-kind="link"
        onClick={() => {
          onOpen?.(row);
        }}
        className={cn(KV, LINK_ROW, "text-left")}
      >
        {key}
        <span className="ml-auto min-w-0 truncate text-right text-ink">{row.value}</span>
        <Icon
          name={trail === "arrow" ? "arrow-right" : "chevron-right"}
          size={12}
          className="text-ink-3"
        />
      </button>
    );
  }
  if (kind === "person") {
    return (
      <div data-record="kv" data-kind="person" className={KV}>
        {key}
        <Menu
          label={row.label}
          width={240}
          align="end"
          trigger={
            <button
              type="button"
              aria-label={`${row.label}: ${row.value}`}
              className="ml-auto flex min-w-0 items-center gap-[6px] rounded-pill px-[4px] hover:bg-nested"
            >
              <Icon name="circle-user-round" size={14} className="text-ink-3" />
              <span className="truncate text-ink">{row.value}</span>
              <Icon name="chevron-down" size={12} className="text-ink-3" />
            </button>
          }
          sections={[
            people.map((name) => ({
              label: name,
              checked: name === row.value,
              onSelect: () => {
                if (name !== row.value) onAssign?.(row, name);
              },
            })),
          ]}
        />
      </div>
    );
  }
  return (
    <div data-record="kv" data-kind="text" className={KV}>
      {key}
      <span className="ml-auto min-w-0 truncate text-right text-ink">{row.value}</span>
    </div>
  );
}

export interface RecordSummaryProps {
  /** The header line ("August 2026 Close"). */
  period?: string;
  status?: string;
  transitions?: Readonly<Record<string, readonly string[]>>;
  stats?: readonly RecordStat[];
  groups?: readonly KvGroup[];
  linkTrail?: "chevron" | "arrow";
  people?: readonly string[];
  onOpen?: (row: RecordStat | KvRow) => void;
  onStatus?: (next: string, prev: string) => void;
  onAssign?: (row: KvRow, name: string) => void;
}

/** The close summary: a centred header with the status pill, stat rows, then banded KV groups. */
export function RecordSummary({
  period,
  status,
  transitions,
  stats = [],
  groups = [],
  linkTrail,
  people,
  onOpen,
  onStatus,
  onAssign,
}: RecordSummaryProps): JSX.Element {
  return (
    <div data-record="summary" className="flex flex-col">
      {(period !== undefined || status !== undefined) && (
        <div className="flex flex-col items-center px-[12px] pt-[16px] pb-[14px] text-center hairline-b">
          {period !== undefined && (
            <p className="text-pane font-medium tracking-[-0.012em]">{period}</p>
          )}
          {status !== undefined && (
            <span className="mt-[8px]">
              <StatusDropdownPill
                status={status}
                {...(transitions === undefined ? {} : { transitions })}
                {...(onStatus === undefined ? {} : { onStatus })}
              />
            </span>
          )}
        </div>
      )}
      {stats.map((stat) => (
        <StatRow key={stat.id} stat={stat} {...(onOpen === undefined ? {} : { onOpen })} />
      ))}
      {groups.map((group, i) => (
        <div key={group.title ?? String(i)} className="flex flex-col">
          {group.title !== undefined && <RecordBand title={group.title} />}
          {group.rows.map((row) => (
            <KvRowView
              key={row.id}
              row={row}
              {...(linkTrail === undefined ? {} : { linkTrail })}
              {...(people === undefined ? {} : { people })}
              {...(onOpen === undefined ? {} : { onOpen })}
              {...(onAssign === undefined ? {} : { onAssign })}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
