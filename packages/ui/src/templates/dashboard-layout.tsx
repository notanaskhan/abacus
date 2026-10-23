import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { FilterChip } from "../components/inputs";
import { Count, Pill, Ring } from "../components/pill";
import { EmptyState, Skeleton } from "../components/states";
import { Icon, type IconName } from "../icons";
import { AppShell } from "../layout/app-shell";
import { Pane } from "../layout/pane";
import type { ToolbarProps } from "../layout/toolbar";
import type { PillVariant } from "../status";

// T11 DashboardLayout (F-05-T46; Wave 0 - Foundations `#t11`, Wave 0 - Templates TPL-11): Home.
// Under the toolbar, the greeting row (20/500 greeting, the date in ink-3, an optional caption
// under them; the Office chip and the running pill at the right); the tile row; then the queue
// pane beside a 420 column of Deadlines over Client activity. No charts; KPI type is 20px (the
// `dashboard` role), never above 22.
//
// The dashboard computes nothing. Every count arrives in the props (the screen's read model, from
// the server); the office filter is the caller's, which hands back the view for that office.
// Agent proposals are rows "proposed by Accrued Agent" for a named person to open: Home offers no
// decide action, so a queue row is a link and never a decision control.

export interface DashboardOffice {
  label: string;
  options: readonly string[];
  /** The chosen office, or null for all of them. */
  value: string | null;
  allLabel: string;
  onChange?: (office: string | null) => void;
}

export interface DashboardLayoutProps {
  toolbar: ToolbarProps;
  embedded?: boolean;
  height?: number;
  /** "Good morning, Margaret" */
  greeting: string;
  /** "Monday, September 14" */
  date: string;
  /** Under the greeting, 11.5 ink-3: "Tax returns · TY2025 · 79 open". */
  caption?: string;
  office?: DashboardOffice;
  /** "3 running": the agent sessions running now, from the server. */
  running?: string;
  /** Skeleton tiles and rows while the read model loads (T11f). */
  loading?: boolean;
  /** The tile row: `DashTile`s. */
  tiles?: ReactNode;
  /** The left pane: "Waiting on you" with its queue. */
  queue: { title: string; count?: number; children: ReactNode };
  /** The right column, top to bottom: Deadlines, then Client activity. */
  side: readonly { title: string; children: ReactNode }[];
}

// ---- Tiles ----------------------------------------------------------------------------------------

export type DashTileProps =
  | {
      /** A number over its status pill, centred, 120 wide (T11, TPL-11 tax tiles). */
      kind: "single";
      value: string;
      label: string;
      variant: PillVariant;
    }
  | {
      /** A title over a row of numbers with their captions (TY2025 Returns, Audits). */
      kind: "group";
      title: string;
      counts: readonly { value: string; label: string }[];
      /** A fixed width (TPL-11's 360 audits tile); otherwise the group shares the row. */
      width?: number;
    }
  | {
      /** A number with a pill beside it and a caption under (TPL-11 Closes, Notices). */
      kind: "meter";
      value: string;
      pill?: { label: string; variant: PillVariant };
      caption: string;
    }
  | {
      /** A number over a caption, left (TPL-11d: "17 Signatures out"). */
      kind: "stat";
      value: string;
      caption: string;
    };

const TILE = "flex min-h-[98px] flex-col rounded-pane bg-card shadow-e1";

/** One Home tile. The number is the `dashboard` type role (20px); words carry every state. */
export function DashTile(props: DashTileProps): JSX.Element {
  if (props.kind === "single") {
    return (
      <section
        data-tile="single"
        aria-label={`${props.value} ${props.label}`}
        className={cn(TILE, "w-[120px] flex-none items-center justify-center gap-[6px]")}
      >
        <span className="text-dashboard font-medium">{props.value}</span>
        <Pill variant={props.variant} size="state">
          {props.label}
        </Pill>
      </section>
    );
  }
  if (props.kind === "group") {
    return (
      <section
        data-tile="group"
        aria-label={props.title}
        {...(props.width === undefined ? {} : { style: { width: props.width } })}
        className={cn(
          TILE,
          "min-w-0 gap-[8px] px-[16px] pt-[14px] pb-[12px]",
          props.width === undefined ? "flex-[1_1_0%]" : "flex-none",
        )}
      >
        <h3 className="text-body font-medium">{props.title}</h3>
        <ul className="flex flex-wrap gap-x-[18px] gap-y-[4px]">
          {props.counts.map((c) => (
            <li key={c.label} className="flex max-w-[64px] flex-col">
              <span className="text-[15px] leading-[18px] font-medium">{c.value}</span>
              <span className="text-meta text-ink-3">{c.label}</span>
            </li>
          ))}
        </ul>
      </section>
    );
  }
  if (props.kind === "meter") {
    return (
      <section
        data-tile="meter"
        aria-label={`${props.value} ${props.pill?.label ?? ""} ${props.caption}`.replace(
          "  ",
          " ",
        )}
        className={cn(TILE, "w-[160px] flex-none justify-center gap-[4px] px-[16px]")}
      >
        <span className="flex items-center gap-[8px]">
          <span className="text-dashboard font-medium">{props.value}</span>
          {props.pill !== undefined && (
            <Pill variant={props.pill.variant} size="sm">
              {props.pill.label}
            </Pill>
          )}
        </span>
        <span className="text-meta text-ink-3">{props.caption}</span>
      </section>
    );
  }
  return (
    <section
      data-tile="stat"
      aria-label={`${props.value} ${props.caption}`}
      className={cn(TILE, "w-[160px] flex-none justify-center gap-[4px] px-[16px]")}
    >
      <span className="text-dashboard font-medium">{props.value}</span>
      <span className="text-meta text-ink-3">{props.caption}</span>
    </section>
  );
}

// ---- Rows -----------------------------------------------------------------------------------------

export interface QueueRowProps {
  icon: IconName;
  title: string;
  context: string;
  /** The due or state pill at the right: "Today", "Blocked on a partner decision". */
  due: { label: string; variant: PillVariant };
  /** Where the row goes: the screen that holds the decision. A queue row never decides. */
  href: string;
  /** For readers and the hint: "Opens AUD-07 with the decision card (SHL-11)". */
  hint?: string;
}

/** One item waiting on the viewer: a link to where it is decided, never the decision itself. */
export function QueueRow({ icon, title, context, due, href, hint }: QueueRowProps): JSX.Element {
  return (
    <li>
      <a
        href={href}
        data-queue-row=""
        {...(hint === undefined ? {} : { title: hint })}
        className="flex min-h-[52px] items-center gap-[12px] px-[14px] py-[8px] hairline-b hover:bg-shell"
      >
        <span
          aria-hidden="true"
          className="inline-flex size-[22px] shrink-0 items-center justify-center rounded-full bg-nested text-ink-3"
        >
          <Icon name={icon} size={12} />
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
          <span className="text-body font-medium">{title}</span>
          <span className="text-meta text-ink-3">{context}</span>
        </span>
        <Pill variant={due.variant} size="state" className="shrink-0">
          {due.label}
        </Pill>
        <Icon name="chevron-right" size={13} className="shrink-0 text-ink-3" />
      </a>
    </li>
  );
}

export interface DeadlineRowProps {
  date: string;
  /** Red ink inside a week, amber ink inside the fortnight, ink-2 otherwise (words say it too). */
  dateTone?: "red" | "amber" | "plain";
  client: string;
  form: string;
  status?: { label: string; variant: PillVariant };
  /** In place of the pill: "View all →". */
  link?: { label: string; href: string };
}

const DATE_TONE = { red: "text-red-ink", amber: "text-amber-ink", plain: "text-ink-2" } as const;

export function DeadlineRow({
  date,
  dateTone = "plain",
  client,
  form,
  status,
  link,
}: DeadlineRowProps): JSX.Element {
  return (
    <li
      data-deadline=""
      className="flex min-h-[42px] items-center gap-[12px] px-[12px] py-[5px] hairline-b"
    >
      <span className={cn("w-[44px] shrink-0 text-body font-medium", DATE_TONE[dateTone])}>
        {date}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-body">{client}</span>
        <span className="truncate text-meta text-ink-3">{form}</span>
      </span>
      {link !== undefined ? (
        <a href={link.href} className="shrink-0 text-body font-medium">
          {link.label}
        </a>
      ) : (
        status !== undefined && (
          <Pill variant={status.variant} size="state" className="shrink-0">
            {status.label}
          </Pill>
        )
      )}
    </li>
  );
}

export interface ActivityRowProps {
  icon: IconName;
  text: string;
  /** T11: the client under the text and the time at the right. TPL-11: the time before the text. */
  context?: string;
  when: string;
  layout?: "right" | "lead";
}

export function ActivityRow({
  icon,
  text,
  context,
  when,
  layout = "right",
}: ActivityRowProps): JSX.Element {
  return (
    <li className="flex gap-[10px] px-[12px] py-[7px]">
      <span
        aria-hidden="true"
        className="mt-[1px] inline-flex size-[20px] shrink-0 items-center justify-center rounded-full bg-nested text-ink-3"
      >
        <Icon name={icon} size={12} />
      </span>
      {layout === "lead" ? (
        <span className="min-w-0 flex-1 text-body">
          <span className="text-ink-3">{when} · </span>
          {text}
        </span>
      ) : (
        <>
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="text-body">{text}</span>
            {context !== undefined && <span className="text-meta text-ink-3">{context}</span>}
          </span>
          <span className="shrink-0 text-dense text-ink-2">{when}</span>
        </>
      )}
    </li>
  );
}

/** The quiet day (T11e, TPL-11e): the queue's empty state. */
export function QueueEmpty({ title, children }: { title: string; children: string }): JSX.Element {
  return (
    <EmptyState icon="check" title={title}>
      {children}
    </EmptyState>
  );
}

// ---- Loading --------------------------------------------------------------------------------------

const SKELETON_ROWS = ["62%", "48%", "74%", "56%", "40%", "66%"] as const;

function LoadingTiles(): JSX.Element {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <div key={i} className={cn(TILE, "flex-[1_1_0%] gap-[10px] px-[16px] pt-[16px]")}>
          <Skeleton immediate className="h-[11px] w-[40%]" />
          <Skeleton immediate className="h-[16px] w-[70%]" />
        </div>
      ))}
      {[0, 1].map((i) => (
        <div
          key={`s${String(i)}`}
          className={cn(TILE, "w-[120px] flex-none items-center justify-center gap-[10px]")}
        >
          <Skeleton immediate className="h-[18px] w-[36px]" />
          <Skeleton immediate className="h-[12px] w-[64px]" />
        </div>
      ))}
    </>
  );
}

function LoadingRows(): JSX.Element {
  return (
    <div className="flex flex-col">
      {SKELETON_ROWS.map((w, i) => (
        <div key={w} className="flex flex-col gap-[7px] px-[14px] py-[12px] hairline-b">
          <Skeleton immediate style={{ width: w }} className="h-[11px]" />
          <Skeleton
            immediate
            style={{ width: ["38%", "30%", "44%"][i % 3] }}
            className="h-[9px]"
          />
        </div>
      ))}
    </div>
  );
}

// ---- Layout ---------------------------------------------------------------------------------------

export function DashboardLayout({
  toolbar,
  embedded = false,
  height,
  greeting,
  date,
  caption,
  office,
  running,
  loading = false,
  tiles,
  queue,
  side,
}: DashboardLayoutProps): JSX.Element {
  const head = (
    <div className="relative flex flex-none items-start justify-between px-(--edge-app) pt-[8px]">
      <div className="flex min-h-[42px] flex-col justify-center">
        <p className="flex items-baseline gap-[10px]">
          <span className="text-dashboard font-medium tracking-[-0.015em]">{greeting}</span>
          <span className="text-body text-ink-2">{date}</span>
        </p>
        {caption !== undefined && (
          <p data-dashboard="caption" className="pl-[2px] text-meta text-ink-3">
            {caption}
          </p>
        )}
      </div>
      <div className="flex items-center gap-[8px] pt-[1px]">
        {office !== undefined && (
          <FilterChip
            label={office.label}
            icon="map-pin"
            options={office.options.map((o) => ({ value: o, label: o }))}
            value={office.value}
            placeholder={office.allLabel}
            clearLabel={office.allLabel}
            {...(office.onChange === undefined ? {} : { onChange: office.onChange })}
          />
        )}
        {running !== undefined && (
          <span
            data-dashboard="running"
            className="inline-flex h-[29px] items-center gap-[7px] rounded-pill bg-card pr-[11px] pl-[10px] text-body shadow-e1"
          >
            <Ring size={12} width={1.5} track="stroke-chip" rotate={-140} className="text-ink-2" />
            {running}
          </span>
        )}
      </div>
    </div>
  );
  return (
    <AppShell
      {...(embedded ? { embedded: true } : {})}
      {...(height === undefined ? {} : { height })}
      toolbar={{ active: "Home", ...toolbar }}
      record={
        <>
          {head}
          <div
            data-dashboard="tiles"
            {...(loading ? { "aria-busy": true } : {})}
            className="flex flex-none gap-(--gutter-pane) px-(--edge-app) pt-[6px]"
          >
            {loading ? <LoadingTiles /> : tiles}
          </div>
        </>
      }
    >
      <Pane
        title={queue.title}
        scrollLabel={queue.title}
        {...(queue.count === undefined || loading ? {} : { right: <Count value={queue.count} /> })}
      >
        {loading ? <LoadingRows /> : queue.children}
      </Pane>
      <div className="flex w-[420px] flex-none flex-col gap-(--gutter-pane)">
        {side.map((pane) => (
          <Pane
            key={pane.title}
            title={pane.title}
            scrollLabel={pane.title}
            className="flex-[1_1_0%]"
          >
            {loading ? <LoadingRows /> : pane.children}
          </Pane>
        ))}
      </div>
    </AppShell>
  );
}
