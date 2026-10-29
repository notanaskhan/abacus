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
  /** After the date (HOME-01 R2): "Open Today →" and the Home segmented control. */
  subbar?: ReactNode;
  /** Inside the app's own shell (the routed screen): the subbar, tiles and panes without a second
   * AppShell and toolbar; `toolbar`, `embedded` and `height` are then ignored. */
  bare?: boolean;
  /** Skeleton tiles and rows while the read model loads (T11f). */
  loading?: boolean;
  /** The tile row: `DashTile`s. */
  tiles?: ReactNode;
  /** The left pane: "Waiting on you" with its queue. */
  queue: {
    title: string;
    count?: number;
    /** Beside the count in the pane header: "Open queue →". */
    action?: ReactNode;
    children: ReactNode;
  };
  /** The right column, top to bottom: Deadlines, then Client activity. */
  side: readonly { title: string; children: ReactNode }[];
  /** A fixed height for the first right-hand pane (Deadlines): 334 on T11, 360 on TPL-11. */
  sideTopHeight?: number;
  /** The gap between the queue and the right column: 10 (T11) or 12 (TPL-11). */
  columnsGap?: number;
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

const TILE = "flex h-[99px] flex-col rounded-dialog bg-card shadow-e1";
/** The KPI number: 22/400 tabular, the ceiling F-05 sets for Home (no larger type). */
export const KPI_NUMBER = "text-[22px] leading-[22px] tracking-[-0.01em] tabular-nums";

/** One Home tile (T11, TPL-11): a 99-high card of radius 14; words carry every state. */
export function DashTile(props: DashTileProps): JSX.Element {
  if (props.kind === "single") {
    return (
      <section
        data-tile="single"
        aria-label={`${props.value} ${props.label}`}
        className={cn(TILE, "w-[120px] flex-none items-center justify-center gap-[9px]")}
      >
        <span className={KPI_NUMBER}>{props.value}</span>
        <Pill variant={props.variant} size="state">
          {props.label}
        </Pill>
      </section>
    );
  }
  if (props.kind === "group") {
    const grid = props.width !== undefined;
    return (
      <section
        data-tile="group"
        aria-label={props.title}
        {...(grid ? { style: { width: props.width } } : {})}
        className={cn(
          TILE,
          "min-w-0",
          grid
            ? "flex-none justify-between px-[14px] pt-[12px] pb-[14px]"
            : "flex-[1_1_0%] justify-center gap-[12px] px-[16px]",
        )}
      >
        <h3
          className={cn(
            "whitespace-nowrap",
            grid ? "text-dense font-medium text-ink-2" : "text-body font-medium",
          )}
        >
          {props.title}
        </h3>
        <ul className={grid ? "grid grid-cols-5 gap-[6px]" : "flex gap-[18px]"}>
          {props.counts.map((c) => (
            <li key={c.label} className="flex min-w-0 flex-col gap-[3px]">
              <span className="text-[15px] leading-[18px] tracking-[-0.01em] tabular-nums">
                {c.value}
              </span>
              <span className="text-meta leading-[1.2] text-ink-3">{c.label}</span>
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
        className={cn(TILE, "w-[160px] flex-none justify-center gap-[6px] px-[16px]")}
      >
        <span className="flex items-center gap-[8px]">
          <span className={KPI_NUMBER}>{props.value}</span>
          {props.pill !== undefined && (
            <Pill variant={props.pill.variant} size="state">
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
      className={cn(TILE, "w-[160px] flex-none justify-center gap-[6px] px-[16px]")}
    >
      <span className={KPI_NUMBER}>{props.value}</span>
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
  /** T11's 52-high row (padding 16 at the left) rather than TPL-11's 56. */
  compact?: boolean;
}

/** One item waiting on the viewer: a link to where it is decided, never the decision itself. */
export function QueueRow({
  icon,
  title,
  context,
  due,
  href,
  hint,
  compact = false,
}: QueueRowProps): JSX.Element {
  return (
    <li>
      <a
        href={href}
        data-queue-row=""
        {...(hint === undefined ? {} : { title: hint })}
        className={cn(
          "flex items-center gap-[12px] pr-[12px] hairline-b hover:bg-shell",
          compact ? "h-[52px] pl-[16px]" : "min-h-[56px] py-[8px] pl-[14px]",
        )}
      >
        <span
          aria-hidden="true"
          className="inline-flex size-[22px] shrink-0 items-center justify-center rounded-full bg-nested text-ink-3"
        >
          <Icon name={icon} size={12} />
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span className="text-body leading-[1.3] font-medium">{title}</span>
          <span className="text-meta leading-[1.4] text-ink-3">{context}</span>
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
      className="flex min-h-[40px] items-center gap-[10px] px-[12px] py-[5px] hairline-b"
    >
      <span
        className={cn(
          "w-[46px] shrink-0 text-dense font-medium tabular-nums",
          DATE_TONE[dateTone],
        )}
      >
        {date}
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-[1px]">
        <span className="truncate text-body leading-[15px]">{client}</span>
        <span className="truncate text-meta leading-[14px] text-ink-3">{form}</span>
      </span>
      {link !== undefined ? (
        <a href={link.href} className="shrink-0 text-dense font-medium whitespace-nowrap">
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
    <li
      className={cn(
        "flex min-h-[44px]",
        layout === "lead"
          ? "items-start gap-[10px] px-[12px] py-[6px]"
          : "items-center gap-[12px] px-[14px]",
      )}
    >
      <span
        aria-hidden="true"
        className="mt-[1px] inline-flex size-[20px] shrink-0 items-center justify-center rounded-full bg-nested text-ink-3"
      >
        <Icon name={icon} size={12} />
      </span>
      {layout === "lead" ? (
        <span className="min-w-0 flex-1 text-dense leading-[1.45]">
          <span className="text-ink-3 tabular-nums">{when} · </span>
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
    <div aria-busy="true" data-dashboard="loading" className="flex flex-col">
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
  subbar,
  bare = false,
  loading = false,
  tiles,
  queue,
  side,
  sideTopHeight,
  columnsGap = 10,
}: DashboardLayoutProps): JSX.Element {
  const head = (
    <div
      data-dashboard="subbar"
      className="flex h-[42px] flex-none items-center gap-[10px] px-(--edge-app)"
    >
      <span className="text-[20px] leading-[1.2] font-medium tracking-[-0.015em] whitespace-nowrap">
        {greeting}
      </span>
      <span className="text-body whitespace-nowrap text-ink-3">{date}</span>
      {subbar}
      <span className="flex-1" />
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
          className="inline-flex h-[29px] flex-none items-center gap-[7px] rounded-pill bg-card pr-[12px] pl-[10px] text-body whitespace-nowrap shadow-e1"
        >
          <Ring size={12} width={1.5} track="stroke-chip" rotate={-140} className="text-ink-2" />
          {running}
        </span>
      )}
    </div>
  );
  const record = (
    <>
      {head}
      <div
        data-dashboard="tiles"
        {...(loading ? { "aria-busy": true } : {})}
        className="relative flex h-[109px] flex-none gap-[8px] px-(--edge-app) pt-[10px]"
      >
        {caption !== undefined && (
          <p
            data-dashboard="caption"
            className="absolute top-[-9px] left-[14px] text-dense whitespace-nowrap text-ink-3"
          >
            {caption}
          </p>
        )}
        {loading ? <LoadingTiles /> : tiles}
      </div>
    </>
  );
  const right =
    queue.count === undefined || loading ? (
      queue.action
    ) : (
      <span className="flex items-center gap-[10px]">
        <Count value={queue.count} />
        {queue.action}
      </span>
    );
  const panes = (
    <>
      <Pane
        title={queue.title}
        scrollLabel={queue.title}
        {...(right === undefined ? {} : { right })}
      >
        {loading ? <LoadingRows /> : queue.children}
      </Pane>
      <div
        data-dashboard="side"
        style={columnsGap === 10 ? undefined : { marginLeft: columnsGap - 10 }}
        className="flex w-[420px] flex-none flex-col gap-(--gutter-pane)"
      >
        {side.map((pane, i) => {
          const fixed = i === 0 && sideTopHeight !== undefined;
          return (
            <div
              key={pane.title}
              style={fixed ? { height: sideTopHeight } : undefined}
              className={cn("flex min-h-0", fixed ? "flex-none" : "flex-[1_1_0%]")}
            >
              <Pane title={pane.title} scrollLabel={pane.title}>
                {loading ? <LoadingRows /> : pane.children}
              </Pane>
            </div>
          );
        })}
      </div>
    </>
  );
  if (bare) {
    return (
      <div data-dashboard="bare" className="flex min-h-0 flex-1 flex-col">
        {record}
        <div className="flex min-h-0 flex-1 items-stretch gap-(--gutter-pane) px-(--edge-app) pt-(--gutter-pane) pb-(--edge-app)">
          {panes}
        </div>
      </div>
    );
  }
  return (
    <AppShell
      {...(embedded ? { embedded: true } : {})}
      {...(height === undefined ? {} : { height })}
      toolbar={{ active: "Home", ...toolbar }}
      record={record}
    >
      {panes}
    </AppShell>
  );
}
