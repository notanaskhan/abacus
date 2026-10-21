import clsx from "clsx";
import {
  type HTMLAttributes,
  type JSX,
  type ReactNode,
  useEffect,
  useState,
  useSyncExternalStore,
} from "react";
import { cn } from "../cn";
import { SEP, viaAgent } from "../format";
import { Icon, type IconName } from "../icons";
import { useMotion } from "../motion";
import { Button } from "./button";
import { LiveDot, PULSE_STAGGER_MS, Pulse, Spinner } from "./motion";
import { StatusDisc } from "./status";

// Feedback states (C-20 States kit; F-05-T19): EmptyState, Skeleton, ErrorRow, WaitingBadge,
// AgentRunningRow, the offline banner and the fieldset's empty line. The rules, from the bundle:
// the layout never jumps (a loading, empty or failed pane keeps its header, its column heads and
// its real row heights); a skeleton waits 200ms and never shimmers; an empty state says what will
// appear and what to do, with at most one action; an error is the same state in the brick tint,
// never a red pane; and the Agent is "Accrued Agent", never a person. Under reduced motion
// nothing animates: the pulse, the dot, the crossfade and the spinner draw their still form.
//
// Every colour is a token. The numbers in STATE_GEOMETRY are the bundle's, product px.

// ---------------------------------------------------------------------------------------------
// Geometry and copy

/**
 * The heights a pane keeps in every mode (C-20 spec 1 and 2). `header` is the pane header,
 * `--pane-hd-h`; the rest are row heights, shared by the loaded row and its skeleton so that
 * neither can drift from the other. `card` is a KPI tile (C-19), the card skeleton's height.
 */
export const STATE_GEOMETRY = {
  header: 46,
  list: 48,
  tableHead: 30,
  tableRow: 40,
  task: 50,
  card: 88,
  banner: 32,
} as const;

/** The skeleton waits this long, so a fast load never flashes (C-20). */
export const SKELETON_DELAY_MS = 200;

export type SkeletonType = "list" | "table" | "tasks" | "chat" | "card";

/** Rows (or bubbles, or tiles) a skeleton draws, matching the loaded type so the pane never jumps. */
export const SKELETON_COUNT: Readonly<Record<SkeletonType, number>> = {
  list: 6,
  table: 6,
  tasks: 5,
  chat: 1,
  card: 4,
};

/** Title bars cycle 62, 38, 74 percent; meta bars 38, 74, 62. */
export const SKELETON_TITLE_WIDTHS = ["62%", "38%", "74%"] as const;
export const SKELETON_META_WIDTHS = ["38%", "74%", "62%"] as const;

/** The words of this kit. Typographic apostrophes, as the handoff sets them. */
export const STATE_COPY = {
  offline: "You’re offline. Changes will sync when you reconnect.",
  loading: "Loading",
  errorBody: "Accrued could not reach the server. Nothing was lost; try again in a moment.",
  // The portal never shows the product's name (DEC-01, ADR-133).
  errorBodyPortal: "We could not reach the server. Nothing was lost; try again in a moment.",
  retry: "Retry",
  viewRun: "View run",
  clearFilters: "Clear filters",
  running: "Running…",
  queued: "Queued",
  agentRunning: "Accrued Agent is running",
} as const;

// ---------------------------------------------------------------------------------------------
// The 200ms wait

/** False for `ms` after mount, then true. `immediate` shows it at once (a forced state, a test). */
export function useDelayedShow(ms: number = SKELETON_DELAY_MS, immediate = false): boolean {
  const [shown, setShown] = useState(immediate || ms <= 0);
  useEffect(() => {
    if (shown) return;
    const timer = setTimeout(() => {
      setShown(true);
    }, ms);
    return () => {
      clearTimeout(timer);
    };
  }, [shown, ms]);
  return shown;
}

// ---------------------------------------------------------------------------------------------
// EmptyState

export type EmptyTone = "neutral" | "error";

interface EmptyBase {
  /** What is not here: "No sessions yet." */
  title: string;
  /** What will appear and what to do, in one or two lines. */
  children?: ReactNode;
  /** A registry icon in the 34px tile. Default: the inbox. */
  icon?: IconName;
  /** `error` is the brick tint, for a pane that could not load. Never a red pane. */
  tone?: EmptyTone;
  className?: string;
}

/**
 * At most one action: a secondary button (`action`) or, for a filtered empty, a text link
 * (`link`). Never both, never two; the union makes that a type error.
 */
export type EmptyStateProps = EmptyBase &
  ({ action?: ReactNode; link?: undefined } | { link?: ReactNode; action?: undefined });

/**
 * An empty state (C-20): a 34px tile, a 14/500 title, 12.5 ink-2 words and at most one action,
 * centred in the body it fills. No illustration, no mascot, no cheer. The older `EmptyState` of
 * the app is this component: `title`, `children` and `action` mean what they did.
 */
export function EmptyState({
  title,
  children,
  icon = "inbox",
  tone = "neutral",
  action,
  link,
  className,
}: EmptyStateProps): JSX.Element {
  return (
    <div
      data-empty={tone}
      className={cn("flex flex-1 items-center justify-center px-[20px] py-[24px]", className)}
    >
      <div className="flex max-w-[320px] flex-col items-center text-center">
        <span
          aria-hidden="true"
          className={cn(
            "flex size-[34px] items-center justify-center rounded-tile",
            tone === "error" ? "bg-red-tint text-red-ink" : "bg-nested text-ink-3",
          )}
        >
          <Icon name={icon} size={17} />
        </span>
        <p className="mt-[10px] text-tab font-medium">{title}</p>
        {children !== undefined && (
          <div className="mt-[4px] text-para text-pretty text-ink-2">{children}</div>
        )}
        {link !== undefined && <div className="mt-[6px]">{link}</div>}
        {action !== undefined && <div className="mt-[12px]">{action}</div>}
      </div>
    </div>
  );
}

/** The text link of a filtered empty ("Clear filters"): 12.5 / 500, ink. */
export function EmptyLink({
  children,
  onClick,
  href,
}: {
  children: ReactNode;
  onClick?: () => void;
  href?: string;
}): JSX.Element {
  if (href !== undefined) {
    return (
      <Button asChild variant="link" size="sm" className="font-medium text-ink">
        <a href={href}>{children}</a>
      </Button>
    );
  }
  return (
    <Button
      variant="link"
      size="sm"
      className="font-medium text-ink"
      {...(onClick === undefined ? {} : { onClick })}
    >
      {children}
    </Button>
  );
}

export interface ErrorStateProps {
  /** What failed to load, lower case: "sessions" gives "Couldn’t load sessions." */
  noun?: string;
  /** The whole title, when the noun is not enough. */
  title?: string;
  /** The cause and the reassurance. Default is the handoff's line for the audience. */
  children?: ReactNode;
  /** The portal's line never says "Accrued". */
  audience?: "firm" | "portal";
  /** Retry the load. The caller shows the loading state, then the result. */
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

/**
 * The pane-level error (C-20): the same empty state with a brick-tinted tile, "Couldn’t load …",
 * a line that says nothing was lost, and Retry. The pane stays white; nothing is a red field.
 */
export function ErrorState({
  noun,
  title,
  children,
  audience = "firm",
  onRetry,
  retryLabel = STATE_COPY.retry,
  className,
}: ErrorStateProps): JSX.Element {
  const heading = title ?? `Couldn’t load ${noun ?? "this view"}.`;
  const body =
    children ?? (audience === "portal" ? STATE_COPY.errorBodyPortal : STATE_COPY.errorBody);
  return (
    <div role="alert" className="flex flex-1 flex-col">
      <EmptyState
        tone="error"
        icon="circle-alert"
        title={heading}
        {...(className === undefined ? {} : { className })}
        {...(onRetry === undefined
          ? {}
          : {
              action: (
                <Button variant="secondary" size="md" onClick={onRetry}>
                  {retryLabel}
                </Button>
              ),
            })}
      >
        {body}
      </EmptyState>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Skeleton

function Bar({
  width,
  small = false,
  className,
}: {
  width?: string;
  small?: boolean;
  className?: string;
}): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "block bg-nested",
        small ? "h-[7px] rounded-[3.5px]" : "h-[9px] rounded-[4.5px]",
        className,
      )}
      {...(width === undefined ? {} : { style: { width } })}
    />
  );
}

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  /** Draw it at once instead of after 200ms. */
  immediate?: boolean;
  /** The reduced-motion form whatever the preference: no pulse. */
  still?: boolean;
}

/**
 * A loading bar or block on the nested fill (C-20). It is invisible for the first 200ms (it holds
 * its place, so nothing shifts) and then pulses 1, .55, 1 over 1.2s; never a shimmer. Under
 * reduced motion it does not pulse. Size it with `className` (`h-16`, `w-[62%]`).
 */
export function Skeleton({
  immediate = false,
  still = false,
  className,
  ...props
}: SkeletonProps): JSX.Element {
  const animate = useMotion(still);
  const shown = useDelayedShow(SKELETON_DELAY_MS, immediate);
  return (
    <div
      aria-hidden="true"
      data-pulse={animate ? "skeleton" : "still"}
      className={clsx(
        "min-h-[9px] rounded-[4.5px] bg-nested",
        animate && "animate-pulse",
        !shown && "invisible",
        className,
      )}
      {...props}
    />
  );
}

export interface SkeletonRowsProps {
  type: SkeletonType;
  /** How many; default is the kit's count for the type. */
  count?: number;
  /**
   * A table's grid template, to match its real header. Default is the kit's files table: a wide
   * name, a folder, a 70px date and a 64px size.
   */
  columns?: string;
  immediate?: boolean;
  still?: boolean;
  /** The accessible name of the loading region. */
  label?: string;
  className?: string;
}

const TABLE_COLUMNS = "minmax(0,1.4fr) minmax(0,1fr) 70px 64px";

/**
 * The body of a loading pane (C-20): rows of the loaded type and height, each 70ms behind the one
 * before, drawn after 200ms. The header and the column heads stay real; only the rows are bars.
 * Never a spinner for a whole pane. The region is `aria-busy` and named "Loading".
 */
export function SkeletonRows({
  type,
  count = SKELETON_COUNT[type],
  columns = TABLE_COLUMNS,
  immediate = false,
  still = false,
  label = STATE_COPY.loading,
  className,
}: SkeletonRowsProps): JSX.Element {
  const shown = useDelayedShow(SKELETON_DELAY_MS, immediate);
  const rows = Array.from({ length: count }, (_, i) => i);
  const title = (i: number): string => SKELETON_TITLE_WIDTHS[i % 3] ?? "62%";
  const meta = (i: number): string => SKELETON_META_WIDTHS[i % 3] ?? "38%";
  const hair = "border-b-[0.5px] border-hair";
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={label}
      data-skeleton={type}
      data-shown={shown ? "true" : "false"}
      className={cn(
        type === "card" ? "grid grid-cols-4 gap-[10px] p-[10px]" : "flex flex-col",
        !shown && "invisible",
        className,
      )}
    >
      {rows.map((i) => {
        switch (type) {
          case "list":
            return (
              <Pulse
                key={i}
                index={i}
                still={still}
                data-row="list"
                className={cn("flex flex-col justify-center gap-[6px] px-[12px]", hair)}
                style={{ minHeight: STATE_GEOMETRY.list }}
              >
                <Bar width={title(i)} />
                <Bar small width={meta(i)} />
              </Pulse>
            );
          case "table":
            return (
              <Pulse
                key={i}
                index={i}
                still={still}
                data-row="table"
                className={cn("grid items-center gap-[12px] px-[14px]", hair)}
                style={{ height: STATE_GEOMETRY.tableRow, gridTemplateColumns: columns }}
              >
                <Bar width={title(i)} />
                <Bar small width={meta(i)} />
                <Bar small width="70%" />
                <Bar small width="60%" className="justify-self-end" />
              </Pulse>
            );
          case "tasks":
            return (
              <Pulse
                key={i}
                index={i}
                still={still}
                data-row="tasks"
                className={cn("flex items-center gap-[10px] py-[8px] pr-[12px] pl-[13px]", hair)}
                style={{ minHeight: STATE_GEOMETRY.task }}
              >
                <span aria-hidden="true" className="size-[15px] shrink-0 rounded-pill bg-nested" />
                <span className="flex flex-1 flex-col gap-[6px]">
                  <Bar width={title(i)} />
                  <Bar small width={meta(i)} />
                </span>
              </Pulse>
            );
          case "chat":
            return (
              <Pulse
                key={i}
                index={i}
                still={still}
                data-row="chat"
                className="m-[16px] flex flex-col gap-[10px] rounded-dialog bg-card pt-[14px] pr-[16px] pb-[15px] pl-[16px] shadow-e2"
              >
                <Bar width="74%" />
                <Bar width="62%" />
                <Bar width="38%" />
              </Pulse>
            );
          case "card":
            return (
              <Pulse
                key={i}
                index={i}
                still={still}
                data-row="card"
                className="flex flex-col gap-[5px] rounded-pane bg-card px-[14px] py-[12px] shadow-e1"
                style={{ minHeight: STATE_GEOMETRY.card }}
              >
                <Bar small width="38%" />
                <Bar width="62%" className="mt-[4px] h-[18px]" />
                <Bar small width="74%" className="mt-[4px]" />
              </Pulse>
            );
        }
      })}
    </div>
  );
}

/** The widths and delays a skeleton draws for `type`; the rule, as data, for tests and callers. */
export function skeletonRows(
  type: SkeletonType,
): { title: string; meta: string; delayMs: number }[] {
  return Array.from({ length: SKELETON_COUNT[type] }, (_, i) => ({
    title: SKELETON_TITLE_WIDTHS[i % 3] ?? "62%",
    meta: SKELETON_META_WIDTHS[i % 3] ?? "38%",
    delayMs: i * PULSE_STAGGER_MS,
  }));
}

// ---------------------------------------------------------------------------------------------
// The live dot

export interface AgentLiveProps {
  /** True while anything in the pane runs. Nothing is drawn otherwise. */
  running: boolean;
  still?: boolean;
  className?: string;
}

/**
 * The pane header's 8px olive dot while the Accrued Agent works (C-20). It breathes; it is
 * decoration, so the words ("Accrued Agent is running") are there for assistive technology.
 */
export function AgentLive({
  running,
  still = false,
  className,
}: AgentLiveProps): JSX.Element | null {
  if (!running) return null;
  return (
    <span role="status" className={cn("inline-flex shrink-0", className)}>
      <LiveDot still={still} />
      <span className="sr-only">{STATE_COPY.agentRunning}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------------------------
// Rows: WaitingBadge, ErrorRow, AgentRunningRow

export type RunState = "queued" | "run" | "done" | "wait" | "fail";

export interface RunRowView {
  disc: { idle: "run" | "todo"; end: "done" | "fail" | "wait" | "todo"; settled: boolean };
  title: string;
  meta: string;
  waitingBadge: boolean;
  errorRow: boolean;
}

/**
 * What an agent row shows for its state (C-20 `taskView`). The disc crossfades from the idle disc
 * (a ring while queued, a spinner while running) to the end disc; the meta line reads "Queued",
 * "Running…", then the result. A failure swaps the title for the error's own.
 */
export function runRowView(
  state: RunState,
  row: { title: string; meta?: string | undefined; errorTitle?: string | undefined },
): RunRowView {
  const settled = state === "done" || state === "wait" || state === "fail";
  const end =
    state === "done" ? "done" : state === "fail" ? "fail" : state === "wait" ? "wait" : "todo";
  return {
    disc: { idle: state === "run" ? "run" : "todo", end, settled },
    title: state === "fail" ? (row.errorTitle ?? row.title) : row.title,
    meta:
      state === "run"
        ? STATE_COPY.running
        : state === "queued"
          ? STATE_COPY.queued
          : (row.meta ?? ""),
    waitingBadge: state === "wait",
    errorRow: state === "fail",
  };
}

export interface WaitingBadgeProps {
  /** What it waits on: "Blocked on a partner decision", "Waiting on the client". */
  children: ReactNode;
  /** The decision it leads to (C-12). */
  href?: string;
  onOpen?: () => void;
  className?: string;
}

/**
 * An 8px amber dot and an 11.5/500 amber-ink line that links to the decision. A person decides:
 * the badge only points at it. With neither `href` nor `onOpen` it is a plain label.
 */
export function WaitingBadge({
  children,
  href,
  onOpen,
  className,
}: WaitingBadgeProps): JSX.Element {
  const classes = cn(
    "inline-flex items-center gap-[6px] self-start text-pill-card text-amber-ink",
    (href !== undefined || onOpen !== undefined) && "hover:underline",
    className,
  );
  const dot = <span aria-hidden="true" className="size-[8px] shrink-0 rounded-pill bg-amber" />;
  if (href !== undefined) {
    return (
      <a href={href} data-waiting="true" className={classes}>
        {dot}
        {children}
      </a>
    );
  }
  if (onOpen !== undefined) {
    return (
      <button type="button" onClick={onOpen} data-waiting="true" className={classes}>
        {dot}
        {children}
      </button>
    );
  }
  return (
    <span data-waiting="true" className={classes}>
      {dot}
      {children}
    </span>
  );
}

const ROW_FRAME =
  "flex items-center gap-[10px] border-b-[0.5px] border-hair py-[8px] pr-[12px] pl-[13px]";

function ErrorActions({
  onRetry,
  onViewRun,
  retryLabel,
  viewRunLabel,
}: {
  onRetry?: (() => void) | undefined;
  onViewRun?: (() => void) | undefined;
  retryLabel: string;
  viewRunLabel: string;
}): JSX.Element | null {
  if (onRetry === undefined && onViewRun === undefined) return null;
  return (
    <div className="flex shrink-0 gap-[4px]">
      {onRetry !== undefined && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
      {onViewRun !== undefined && (
        <Button variant="ghost" size="sm" onClick={onViewRun}>
          {viewRunLabel}
        </Button>
      )}
    </div>
  );
}

export interface ErrorRowProps {
  /** What failed: "Bank feed unavailable". 12.5 / 500 in brick ink. */
  title: string;
  /** The cause, in ink-2: "Front Range Bank connection expired on Sep 12." */
  children?: ReactNode;
  /** Re-run only this one. */
  onRetry?: () => void;
  onViewRun?: () => void;
  retryLabel?: string;
  viewRunLabel?: string;
  className?: string;
}

/**
 * A row-level error (C-20): a red cross disc, the title in brick ink, the cause in ink-2, then
 * Retry and View run. It is also the route's `errorComponent`. Never a full red background.
 */
export function ErrorRow({
  title,
  children,
  onRetry,
  onViewRun,
  retryLabel = STATE_COPY.retry,
  viewRunLabel = STATE_COPY.viewRun,
  className,
}: ErrorRowProps): JSX.Element {
  return (
    <div
      role="alert"
      data-error-row="true"
      className={cn(ROW_FRAME, className)}
      style={{ minHeight: STATE_GEOMETRY.task }}
    >
      <StatusDisc state="fail" size={15} />
      <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
        <p className="text-dense font-medium text-red-ink">{title}</p>
        {children !== undefined && <p className="text-meta text-ink-2">{children}</p>}
      </div>
      <ErrorActions
        onRetry={onRetry}
        onViewRun={onViewRun}
        retryLabel={retryLabel}
        viewRunLabel={viewRunLabel}
      />
    </div>
  );
}

export interface AgentRunningRowProps {
  state: RunState;
  /** The step: "Reconcile Business Savings ••7731". Never "task" in the words around it. */
  title: string;
  /** The result once settled: "0 open · No issues". */
  meta?: string;
  /** The failure's title ("Bank feed unavailable"); the cause is `meta`. */
  errorTitle?: string;
  /** What a waiting row waits on, and where the decision is. */
  waiting?: { label: string; href?: string; onOpen?: () => void };
  /** The person the Agent worked for, shown as "‹person› via Agent" on a running or settled row. */
  actor?: string;
  onRetry?: () => void;
  onViewRun?: () => void;
  /** Place in the list; a row's disc pulse is not staggered, but the list's reveal is. */
  still?: boolean;
  className?: string;
}

/**
 * One step of the Accrued Agent's run (C-20, C-26): a 15px disc, the title, and a meta line. The
 * disc is two layers that crossfade over 180ms, from a ring (queued) or a spinner (running) to
 * done, waiting or failed. Waiting links to the decision a person takes; failed is the error row
 * with Retry (this step only) and View run. The row is at least 50 high in every state.
 */
export function AgentRunningRow({
  state,
  title,
  meta,
  errorTitle,
  waiting,
  actor,
  onRetry,
  onViewRun,
  still = false,
  className,
}: AgentRunningRowProps): JSX.Element {
  const animate = useMotion(still);
  const view = runRowView(state, { title, meta, errorTitle });
  const { settled } = view.disc;
  const fade = animate ? "transition-opacity duration-[180ms]" : undefined;
  const attributed =
    actor !== undefined && state !== "queued" && !view.errorRow
      ? `${view.meta}${SEP}${viaAgent(actor)}`
      : view.meta;
  return (
    <li
      data-state={state}
      data-settled={settled ? "true" : "false"}
      className={cn(ROW_FRAME, className)}
      style={{ minHeight: STATE_GEOMETRY.task }}
    >
      <span className="relative size-[15px] shrink-0" data-disc="crossfade">
        <span
          aria-hidden={settled || state === "run" ? "true" : undefined}
          data-layer="idle"
          className={cn("absolute inset-0 inline-flex", fade, settled && "opacity-0")}
        >
          {view.disc.idle === "run" ? (
            <Spinner label={STATE_COPY.running} size={15} showLabel={false} still={still} />
          ) : (
            <StatusDisc state="todo" size={15} />
          )}
        </span>
        <span
          aria-hidden={settled ? undefined : "true"}
          data-layer="end"
          className={cn("absolute inset-0 inline-flex", fade, !settled && "opacity-0")}
        >
          <StatusDisc state={view.disc.end} size={15} />
        </span>
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
        <p className={cn("text-dense", view.errorRow ? "font-medium text-red-ink" : "text-ink")}>
          {view.title}
        </p>
        {view.waitingBadge && waiting !== undefined ? (
          <WaitingBadge
            {...(waiting.href === undefined ? {} : { href: waiting.href })}
            {...(waiting.onOpen === undefined ? {} : { onOpen: waiting.onOpen })}
          >
            {waiting.label}
          </WaitingBadge>
        ) : (
          <p
            {...(view.errorRow ? { role: "alert" } : {})}
            className={cn("text-meta", view.errorRow ? "text-ink-2" : "text-ink-3")}
          >
            {attributed}
          </p>
        )}
      </div>
      {view.errorRow && (
        <ErrorActions
          onRetry={onRetry}
          onViewRun={onViewRun}
          retryLabel={STATE_COPY.retry}
          viewRunLabel={STATE_COPY.viewRun}
        />
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------------------------
// Offline

function subscribeOnline(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

const onlineNow = (): boolean => typeof navigator === "undefined" || navigator.onLine;

/** False while the browser reports no network. The server and the first render say online. */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribeOnline, onlineNow, () => true);
}

export interface OfflineBannerProps {
  /** Force the state (a specimen, a test); otherwise it follows the browser's network status. */
  offline?: boolean;
  className?: string;
}

/**
 * The offline banner (C-20): 32 high, amber tint, directly under the toolbar, one line. The
 * status region is always mounted, so assistive technology hears the banner when it appears; it
 * holds the bar only while offline.
 */
export function OfflineBanner({ offline, className }: OfflineBannerProps): JSX.Element {
  const online = useOnline();
  const isOffline = offline ?? !online;
  return (
    <div role="status" aria-live="polite" data-offline={isOffline ? "true" : "false"}>
      {isOffline && (
        <div
          className={cn(
            "flex items-center justify-center gap-[7px] bg-amber-tint text-dense text-amber-ink",
            className,
          )}
          style={{ height: STATE_GEOMETRY.banner }}
        >
          <Icon name="circle-alert" size={13} />
          <span>{STATE_COPY.offline}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Fieldset empty

/**
 * The one line of a fieldset with no rows (C-20): 12.5 ink-3, "No inputs. This agent runs without
 * a form." Put it in a `flush` Fieldset under its 33px head.
 */
export function FieldsetEmpty({ children }: { children: ReactNode }): JSX.Element {
  return <p className="px-[12px] pt-[11px] pb-[12px] text-dense text-ink-3">{children}</p>;
}
