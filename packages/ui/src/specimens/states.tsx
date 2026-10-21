import { type JSX, type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "../components/button";
import { Fieldset } from "../components/fieldset";
import { Segmented } from "../components/tabs";
import {
  AgentLive,
  AgentRunningRow,
  EmptyLink,
  EmptyState,
  ErrorRow,
  ErrorState,
  FieldsetEmpty,
  OfflineBanner,
  type RunState,
  STATE_COPY,
  STATE_GEOMETRY,
  Skeleton,
  SkeletonRows,
  type SkeletonType,
  WaitingBadge,
} from "../components/states";
import {
  READ_ONLY_REASONS,
  RESTRICTED_COPY,
  FlagOffState,
  RestrictedState,
  type ViewState,
  ViewStateBody,
} from "../components/view-state";
import { viaAgent } from "../format";
import type { IconName } from "../icons";
import { Icon } from "../icons";
import { Held, Row, Sheet } from "./frame";

// The C-20 States kit's specimens (F-05-T19): the six panes with their preview toggle, every kind
// in every mode (forced, with the skeleton drawn at once), the empty and error copy, the agent
// running row live and frozen, the offline banner and the fieldset's empty line, and the
// restricted and flag-off states. The toggle is a preview control: it belongs here and in design
// tools, never in the product (C-20 README). Names, rows and amounts are the handoff's own
// sample, kept in this file and never imported by an app (frontend rule 5); the one change is
// that the Agent is "Accrued Agent", never a person.

export type PaneKind = "sessions" | "issues" | "requests" | "files" | "chat" | "tasks";
export type PaneMode = "loaded" | "loading" | "empty" | "error";

const MODE_LABELS = ["Loaded", "Loading", "Empty", "Error"] as const;
const MODE_OF: Record<string, PaneMode> = {
  Loaded: "loaded",
  Loading: "loading",
  Empty: "empty",
  Error: "error",
};
const LABEL_OF: Record<PaneMode, string> = {
  loaded: "Loaded",
  loading: "Loading",
  empty: "Empty",
  error: "Error",
};

/** The demo's Retry shows Loading, then Loaded, after this long (C-20 `RETRY_LOADING_MS`). */
export const RETRY_LOADING_MS = 900;

interface KindSpec {
  title: string;
  rows: SkeletonType;
  /** The noun of "Couldn’t load …". */
  noun: string;
  icon: IconName;
  empty: { title: string; body?: string; action?: string };
}

const KINDS: Record<PaneKind, KindSpec> = {
  sessions: {
    title: "Sessions",
    rows: "list",
    noun: "sessions",
    icon: "message-square",
    empty: {
      title: "No sessions yet.",
      body: "Ask Workbench to prepare a report, chase documents or run a workpaper.",
      action: "New session",
    },
  },
  issues: {
    title: "Issues",
    rows: "list",
    noun: "issues",
    icon: "flag",
    empty: {
      title: "No open issues.",
      body: "Issues raised by the Accrued Agent or reviewers appear here.",
    },
  },
  requests: {
    title: "Documents",
    rows: "list",
    noun: "documents",
    icon: "circle-check",
    empty: { title: "You’re all caught up.", body: "Your firm hasn’t requested anything new." },
  },
  files: {
    title: "Files",
    rows: "table",
    noun: "files",
    icon: "search",
    empty: { title: "No results for ‘Schwab’." },
  },
  chat: {
    title: "Sep 15 extension tracker by office",
    rows: "chat",
    noun: "this session",
    icon: "message-square",
    empty: {
      title: "No messages yet.",
      body: "Ask about any client, engagement or return. Accrued Agent works read-only until you approve a change.",
    },
  },
  tasks: {
    title: "Close agent",
    rows: "tasks",
    noun: "steps",
    icon: "list-checks",
    empty: {
      title: "No steps yet.",
      body: "Run the close agent to reconcile accounts and raise issues for review.",
      action: "Run close agent",
    },
  },
};

const SESSIONS: readonly (readonly [string, string])[] = [
  ["Sep 15 extension tracker by office", "9:21 AM · Hannah Leclerc"],
  ["Ridgeline 1065 K-1 review", `8:47 AM · ${viaAgent("Hannah Leclerc")}`],
  ["August close · Copperleaf", "Yesterday · Simone Baptiste"],
  ["Northwind 401(k) SOC 1 coverage", `Yesterday · ${viaAgent("Hannah Leclerc")}`],
  ["Granite Peak AP leadsheet", "2 Days Ago · Hannah Leclerc"],
];
const ISSUES: readonly (readonly [string, string])[] = [
  [
    "Related-party balances: counterparties, terms and Section 7872 interest",
    "Waiting on the client",
  ],
  ["704(b) capital for Juno Okafor is off by $8,500", "Review point"],
  [
    "Colorado apportionment: payroll factor uses a draft wage file",
    "The Accrued Agent can fix this",
  ],
];
const DOCUMENTS: readonly (readonly [string, string])[] = [
  ["2025 W-2 From Hudson Yards Dental Group", "Requested Jul 5"],
  ["2025 Form 1098 From Rocket Mortgage LLC", "Requested Jul 5"],
  ["2025 Form 5498-SA From HealthEquity", "Requested Jul 5"],
];
const FILES: readonly (readonly [string, string, string, string])[] = [
  ["2025 Composite 1099 — Brokerage.pdf", "Whitcombe › 2025 Binder › Income", "Sep 15", "1.2 MB"],
  [
    "Harborline Net Trust Assets 12-31-2025.pdf",
    "Northwind 401(k) › Investments",
    "Sep 14",
    "2.4 MB",
  ],
  ["Payroll register · Sep 5, 2026.pdf", "Copperleaf › August close", "Sep 6", "220 KB"],
  ["Tax engagements progress.xlsx", "Workbench › Exports", "Sep 15", "84 KB"],
];

interface TaskSpec {
  title: string;
  meta: string;
  /** The end state and when the demo run settles. */
  end: "done" | "wait" | "fail";
  afterMs: number;
  errorTitle?: string;
  waiting?: string;
}

const TASKS: readonly TaskSpec[] = [
  {
    title: "Recategorize Operating Checking ••4410",
    meta: "0 open · No issues",
    end: "done",
    afterMs: 1400,
  },
  {
    title: "Reconcile Business Savings ••7731",
    meta: "0 open · 1 new issue · Reconciled",
    end: "done",
    afterMs: 2200,
  },
  {
    title: "Post proposed adjustments",
    meta: "",
    end: "wait",
    afterMs: 1800,
    waiting: "Blocked on a partner decision",
  },
  {
    title: "Reconcile Amex Business Card ••1009",
    meta: "Front Range Bank connection expired on Sep 12.",
    end: "fail",
    afterMs: 2600,
    errorTitle: "Bank feed unavailable",
  },
  { title: "Flux review against July", meta: "0 open · No issues", end: "done", afterMs: 3000 },
];

/** Where each step of the close run is: all running, bar the last that waits its turn. */
const MID_RUN: readonly RunState[] = ["done", "run", "run", "run", "queued"];
const SETTLED: readonly RunState[] = TASKS.map((t) => t.end);

/** The demo run: every step starts at once and settles after its own delay. `key` restarts it. */
export function useRunDemo(key: number, freeze?: "mid" | "settled"): readonly RunState[] {
  const [live, setLive] = useState<readonly RunState[]>(() => TASKS.map(() => "run"));
  useEffect(() => {
    if (freeze !== undefined) return;
    setLive(TASKS.map(() => "run"));
    const timers = TASKS.map((task, i) =>
      setTimeout(() => {
        setLive((prev) => prev.map((s, j) => (j === i ? task.end : s)));
      }, task.afterMs),
    );
    return () => {
      timers.forEach(clearTimeout);
    };
  }, [key, freeze]);
  if (freeze === "mid") return MID_RUN;
  if (freeze === "settled") return SETTLED;
  return live;
}

function TaskRows({
  states,
  still,
  onRetry,
}: {
  states: readonly RunState[];
  still?: boolean;
  onRetry?: () => void;
}): JSX.Element {
  return (
    <ul className="flex flex-col">
      {TASKS.map((task, i) => (
        <AgentRunningRow
          key={task.title}
          state={states[i] ?? "queued"}
          title={task.title}
          meta={task.meta}
          still={still === true}
          {...(task.errorTitle === undefined ? {} : { errorTitle: task.errorTitle })}
          {...(task.waiting === undefined
            ? {}
            : { waiting: { label: task.waiting, href: "#decision" } })}
          {...(onRetry === undefined ? {} : { onRetry })}
          onViewRun={() => undefined}
        />
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------------------------
// The loaded rows: the same heights the skeletons hold

function ListRows({
  rows,
  ring = false,
}: {
  rows: readonly (readonly [string, string])[];
  ring?: boolean;
}): JSX.Element {
  return (
    <ul className="flex flex-col">
      {rows.map(([title, meta]) => (
        <li
          key={title}
          data-row="list"
          className="flex items-center gap-[10px] border-b-[0.5px] border-hair px-[12px]"
          style={{ minHeight: STATE_GEOMETRY.list }}
        >
          {ring && (
            <span
              aria-hidden="true"
              className="size-[13px] shrink-0 rounded-pill inset-ring-[1.2px] inset-ring-ink-4"
            />
          )}
          <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
            <span className="truncate text-body">{title}</span>
            <span className="truncate text-meta text-ink-3">{meta}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

const TABLE_GRID = "minmax(0,1.4fr) minmax(0,1fr) 70px 64px";

function FilesHead(): JSX.Element {
  return (
    <div
      data-row="table-head"
      className="grid shrink-0 items-center gap-[12px] border-b-[0.5px] border-hair bg-band-hd px-[14px] text-th text-ink-3"
      style={{ height: STATE_GEOMETRY.tableHead, gridTemplateColumns: TABLE_GRID }}
    >
      <span>Name</span>
      <span>Folder</span>
      <span>Modified</span>
      <span className="text-right">Size</span>
    </div>
  );
}

function FilesRows(): JSX.Element {
  return (
    <ul className="flex flex-col">
      {FILES.map(([name, folder, modified, size]) => (
        <li
          key={name}
          data-row="table"
          className="grid items-center gap-[12px] border-b-[0.5px] border-hair px-[14px] text-body"
          style={{ height: STATE_GEOMETRY.tableRow, gridTemplateColumns: TABLE_GRID }}
        >
          <span className="flex min-w-0 items-center gap-[9px]">
            <Icon name="file-text" size={15} className="text-ink-3" />
            <span className="truncate">{name}</span>
          </span>
          <span className="truncate text-cell text-ink-3">{folder}</span>
          <span className="truncate text-cell text-ink-3">{modified}</span>
          <span className="truncate text-right text-cell text-ink-3">{size}</span>
        </li>
      ))}
    </ul>
  );
}

function ChatRows(): JSX.Element {
  return (
    <div className="flex flex-col">
      <p className="mt-[16px] mr-[16px] max-w-[70%] self-end rounded-dialog bg-espresso px-[14px] py-[10px] text-chat text-on-dark">
        Show me where every 1065 and 1120-S stands against the September 15 extended deadline.
      </p>
      <p className="mx-[16px] mt-[11px] mb-[16px] rounded-dialog bg-card px-[16px] pt-[13px] pb-[14px] text-chat shadow-e2">
        Discovery is done. 86 of the 119 returns for period 2025 are 1065 or 1120-S, and 52 of them
        are on extension.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// A pane with the kit's preview toggle

function stateOf(kind: PaneKind, mode: PaneMode, retry: () => void): ViewState {
  switch (mode) {
    case "loaded":
      return { kind: "ready" };
    case "loading":
      return { kind: "loading" };
    case "empty":
      // Files is the filtered empty: "No results for ‘Schwab’." and Clear filters.
      return kind === "files"
        ? { kind: "filtered-empty", query: "Schwab" }
        : {
            kind: "empty",
            ...(KINDS[kind].empty.action === undefined
              ? {}
              : { action: { label: KINDS[kind].empty.action, onSelect: () => undefined } }),
          };
    case "error":
      return { kind: "error", retry };
  }
}

export interface StatesPaneProps {
  kind: PaneKind;
  mode: PaneMode;
  /** Called by the toggle and by Retry / Clear filters; omit for a frozen pane. */
  onMode?: (mode: PaneMode) => void;
  /** Hide the preview toggle (`toggle={false}`). */
  toggle?: boolean;
  /** Draw the skeleton at once, as the forced-state boards do. */
  immediate?: boolean;
  /** The reduced-motion form whatever the preference. */
  still?: boolean;
  /** Freeze the close run mid-run or settled; otherwise it plays. */
  freeze?: "mid" | "settled";
  /** Restart the close run. */
  replay?: number;
  height?: number;
}

/**
 * One pane of the kit: a 46px header (live dot, title, preview toggle) over a body in one of four
 * modes. The header and the table head are the same in every mode, and the loaded rows and the
 * skeleton rows are the same height; the pane's own height is fixed, so nothing moves.
 */
export function StatesPane({
  kind,
  mode,
  onMode,
  toggle = true,
  immediate = false,
  still = false,
  freeze,
  replay = 0,
  height = 360,
}: StatesPaneProps): JSX.Element {
  const spec = KINDS[kind];
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(
    () => () => {
      clearTimeout(timer.current);
    },
    [],
  );
  const retry = useCallback((): void => {
    onMode?.("loading");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      onMode?.("loaded");
    }, RETRY_LOADING_MS);
  }, [onMode]);
  const states = useRunDemo(replay, freeze);
  const running = kind === "tasks" && mode === "loaded" && states.includes("run");
  const state = stateOf(kind, mode, retry);
  const filtered: ViewState =
    state.kind === "filtered-empty"
      ? { ...state, clear: () => onMode?.("loaded") }
      : state.kind === "empty" && state.action !== undefined
        ? {
            kind: "empty",
            action: { label: state.action.label, onSelect: () => onMode?.("loaded") },
          }
        : state;
  return (
    <div
      role="group"
      aria-label={spec.title}
      data-pane={kind}
      data-mode={mode}
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
      style={{ height }}
    >
      <header
        data-pane-header="true"
        className="flex shrink-0 items-center gap-[8px] border-b-[0.5px] border-hair pr-[8px] pl-[14px]"
        style={{ height: "var(--pane-hd-h)" }}
      >
        <AgentLive running={running} still={still} />
        <h3 className="min-w-0 flex-1 truncate text-pane font-medium">{spec.title}</h3>
        {toggle && (
          <Segmented
            label="Preview state"
            size="small"
            options={MODE_LABELS}
            active={LABEL_OF[mode]}
            onChange={(label) => {
              onMode?.(MODE_OF[label] ?? "loaded");
            }}
          />
        )}
      </header>
      <ViewStateBody
        state={filtered}
        rows={spec.rows}
        columns={TABLE_GRID}
        immediate={immediate}
        still={still}
        noun={spec.noun}
        empty={{
          icon: spec.icon,
          title: spec.empty.title,
          ...(spec.empty.body === undefined ? {} : { body: spec.empty.body }),
        }}
        head={kind === "files" ? <FilesHead /> : undefined}
      >
        {kind === "sessions" && <ListRows rows={SESSIONS} />}
        {kind === "issues" && <ListRows rows={ISSUES} ring />}
        {kind === "requests" && <ListRows rows={DOCUMENTS} />}
        {kind === "files" && <FilesRows />}
        {kind === "chat" && <ChatRows />}
        {kind === "tasks" && <TaskRows states={states} still={still} onRetry={() => undefined} />}
      </ViewStateBody>
    </div>
  );
}

function LivePane({ kind }: { kind: PaneKind }): JSX.Element {
  const [mode, setMode] = useState<PaneMode>("loaded");
  return <StatesPane kind={kind} mode={mode} onMode={setMode} />;
}

const KIND_ORDER: readonly PaneKind[] = [
  "sessions",
  "issues",
  "requests",
  "files",
  "chat",
  "tasks",
];

export function ViewStateSpecimen(): JSX.Element {
  return (
    <Sheet title="States panes" meta="Header 46 · rows 48 / 40 / 50 · skeleton after 200ms">
      <div className="grid grid-cols-1 gap-[10px] bg-shell p-[10px] lg:grid-cols-2">
        {KIND_ORDER.map((kind) => (
          <LivePane key={kind} kind={kind} />
        ))}
      </div>
    </Sheet>
  );
}

export function ForcedStatesSpecimen(): JSX.Element {
  const kinds: readonly PaneKind[] = ["sessions", "files"];
  const modes: readonly PaneMode[] = ["loaded", "loading", "empty", "error"];
  return (
    <Sheet title="Forced states" meta="Sessions and Files in every mode, skeleton drawn at once">
      <div className="flex flex-col gap-[10px] bg-shell p-[10px]">
        {kinds.map((kind) => (
          <div key={kind} className="grid grid-cols-1 gap-[10px] md:grid-cols-2 xl:grid-cols-4">
            {modes.map((mode) => (
              <StatesPane
                key={mode}
                kind={kind}
                mode={mode}
                toggle={false}
                immediate
                still
                height={320}
              />
            ))}
          </div>
        ))}
        <div className="grid grid-cols-1 gap-[10px] md:grid-cols-2">
          <StatesPane kind="tasks" mode="loaded" toggle={false} freeze="mid" still />
          <StatesPane kind="tasks" mode="loaded" toggle={false} freeze="settled" still />
        </div>
      </div>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------------------------
// EmptyState and the error

export function EmptyStateSpecimen(): JSX.Element {
  return (
    <Sheet title="EmptyState" meta="Tile 34 r8 · title 14/500 · body 12.5 ink-2 · one action">
      {KIND_ORDER.filter((k) => k !== "files").map((kind) => {
        const spec = KINDS[kind];
        return (
          <Row
            key={kind}
            name={kind === "requests" ? "requests (portal)" : kind}
            meaning={spec.empty.action === undefined ? "No action" : "One secondary button"}
          >
            <div className="flex w-[340px] items-center rounded-pane bg-shell">
              <EmptyState
                icon={spec.icon}
                title={spec.empty.title}
                {...(spec.empty.action === undefined
                  ? {}
                  : {
                      action: (
                        <Button variant="secondary" size="md">
                          {spec.empty.action}
                        </Button>
                      ),
                    })}
              >
                {spec.empty.body}
              </EmptyState>
            </div>
          </Row>
        );
      })}
      <Row name="files (filtered)" meaning="A text link, never both">
        <div className="flex w-[340px] items-center rounded-pane bg-shell">
          <EmptyState
            icon="search"
            title="No results for ‘Schwab’."
            link={<EmptyLink>Clear filters</EmptyLink>}
          />
        </div>
      </Row>
      <Row name="Error" meaning="Brick tile, never a red pane">
        <div className="flex w-[340px] items-center rounded-pane bg-shell">
          <ErrorState noun="sessions" onRetry={() => undefined} />
        </div>
      </Row>
      <Row name="Error, portal" meaning="The portal never says Accrued">
        <div className="flex w-[340px] items-center rounded-pane bg-shell">
          <ErrorState noun="documents" audience="portal" onRetry={() => undefined} />
        </div>
      </Row>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------------------------
// Skeleton

const SKELETON_TYPES: readonly SkeletonType[] = ["list", "table", "tasks", "chat", "card"];

export function SkeletonSpecimen(): JSX.Element {
  return (
    <Sheet title="Skeleton" meta="9h and 7h bars · pulse 1 to .55 · rows 70ms apart · after 200ms">
      {SKELETON_TYPES.map((type) => (
        <Row
          key={type}
          name={type}
          meaning={type === "card" ? "KPI tile height" : "Real row height"}
        >
          <div className="w-[420px] overflow-hidden rounded-pane bg-card shadow-e1">
            <SkeletonRows type={type} immediate />
          </div>
          <Held name="Still (reduced motion)">
            <div className="w-[420px] overflow-hidden rounded-pane bg-card shadow-e1">
              <SkeletonRows type={type} immediate still />
            </div>
          </Held>
        </Row>
      ))}
      <Row name="Skeleton block" meaning="Sized by the caller; waits 200ms">
        <Skeleton immediate className="h-16 w-[260px]" />
        <Skeleton immediate still className="h-16 w-[260px]" />
      </Row>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------------------------
// AgentRunningRow, WaitingBadge, ErrorRow

export function AgentRunningRowSpecimen(): JSX.Element {
  const [replay, setReplay] = useState(0);
  const states = useRunDemo(replay);
  const running = states.includes("run");
  return (
    <Sheet title="AgentRunningRow" meta="Row 50 · disc crossfade 180ms · spinner 820ms">
      <Row name="Live run" meaning="Every step starts at once and settles in 1.4 to 3s">
        <div className="flex w-[520px] flex-col overflow-hidden rounded-pane bg-card shadow-e2">
          <header
            className="flex shrink-0 items-center gap-[8px] border-b-[0.5px] border-hair pr-[8px] pl-[14px]"
            style={{ height: "var(--pane-hd-h)" }}
          >
            <AgentLive running={running} />
            <h3 className="min-w-0 flex-1 truncate text-pane font-medium">Close agent</h3>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setReplay((n) => n + 1);
              }}
            >
              Replay run
            </Button>
          </header>
          <TaskRows
            states={states}
            onRetry={() => {
              setReplay((n) => n + 1);
            }}
          />
        </div>
      </Row>
      <Row name="Mid-run, frozen" meaning="One done, three running, one queued">
        <div className="w-[520px] overflow-hidden rounded-pane bg-card shadow-e2">
          <TaskRows states={MID_RUN} still />
        </div>
      </Row>
      <Row name="Settled, frozen" meaning="Done, waiting, failed">
        <div className="w-[520px] overflow-hidden rounded-pane bg-card shadow-e2">
          <TaskRows states={SETTLED} still onRetry={() => undefined} />
        </div>
      </Row>
      <Row name="WaitingBadge" meaning="Links to the decision; a person decides">
        <WaitingBadge href="#decision">Blocked on a partner decision</WaitingBadge>
        <WaitingBadge href="#decision">Waiting on the client</WaitingBadge>
      </Row>
      <Row name="ErrorRow" meaning="Retry re-runs this step only">
        <div className="w-[520px] overflow-hidden rounded-pane bg-card shadow-e2">
          <ErrorRow
            title="Bank feed unavailable"
            onRetry={() => undefined}
            onViewRun={() => undefined}
          >
            Front Range Bank connection expired on Sep 12.
          </ErrorRow>
        </div>
      </Row>
      <Row name="Attributed" meaning="‹person› via Agent, never a persona">
        <div className="w-[520px] overflow-hidden rounded-pane bg-card shadow-e2">
          <ul>
            <AgentRunningRow
              state="run"
              title="Match bank transactions"
              actor="Hannah Leclerc"
              still
            />
            <AgentRunningRow
              state="done"
              title="Draft reconciling entries"
              meta="18 proposed · none posted"
              actor="Hannah Leclerc"
              still
            />
          </ul>
        </div>
      </Row>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------------------------
// Offline and the fieldset's empty line

function ToolbarStrip({ children }: { children: ReactNode }): JSX.Element {
  return (
    <div className="overflow-hidden rounded-pane bg-card shadow-e2">
      <div
        className="flex items-center justify-center border-b-[0.5px] border-hair bg-card text-dense text-ink-3"
        style={{ height: "var(--toolbar-h)" }}
      >
        Toolbar, Closes active
      </div>
      {children}
      <div className="h-[48px] bg-shell" />
    </div>
  );
}

export function OfflineBannerSpecimen(): JSX.Element {
  return (
    <Sheet
      title="Offline banner and fieldset empty"
      meta={`Banner ${String(STATE_GEOMETRY.banner)}h under the toolbar`}
    >
      <Row name="Offline" meaning="role=status, amber tint, one line">
        <div className="w-[560px]">
          <ToolbarStrip>
            <OfflineBanner offline />
          </ToolbarStrip>
        </div>
      </Row>
      <Row name="Online" meaning="Nothing is drawn; the status region stays mounted">
        <div className="w-[560px]">
          <ToolbarStrip>
            <OfflineBanner offline={false} />
          </ToolbarStrip>
        </div>
      </Row>
      <Row name="Fieldset empty" meaning="One 12.5 ink-3 line under a 33h head">
        <div className="w-[560px]">
          <Fieldset title="Inputs" flush>
            <FieldsetEmpty>No inputs. This agent runs without a form.</FieldsetEmpty>
          </Fieldset>
        </div>
      </Row>
      <Row name="Words" meaning="Verbatim from the handoff">
        <span className="text-dense text-ink-2">{STATE_COPY.offline}</span>
      </Row>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------------------------
// Restricted and flag-off

function FramedBody({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <div
      role="group"
      className="flex h-[240px] w-[340px] flex-col overflow-hidden rounded-pane bg-card shadow-e2"
      aria-label={title}
    >
      <header
        className="flex shrink-0 items-center border-b-[0.5px] border-hair px-[14px]"
        style={{ height: "var(--pane-hd-h)" }}
      >
        <h3 className="min-w-0 flex-1 truncate text-pane font-medium">{title}</h3>
      </header>
      {children}
    </div>
  );
}

export function RestrictedStateSpecimen(): JSX.Element {
  return (
    <Sheet title="Restricted" meta="No record data (INV-3, ADR-024) · reason in words">
      {READ_ONLY_REASONS.map((reason) => (
        <Row key={reason} name={reason} meaning={RESTRICTED_COPY[reason].title}>
          <FramedBody title="Granite Peak">
            <ViewStateBody state={{ kind: "restricted", reason }} empty={{ title: "No items." }} />
          </FramedBody>
        </Row>
      ))}
      <Row name="With an action" meaning="One, if the person can do something">
        <FramedBody title="Granite Peak">
          <RestrictedState
            reason="gate_g2"
            title="Simone Baptiste must confirm independence."
            action={
              <Button variant="secondary" size="md">
                Open the confirmation
              </Button>
            }
          />
        </FramedBody>
      </Row>
    </Sheet>
  );
}

export function FlagOffStateSpecimen(): JSX.Element {
  return (
    <Sheet title="Flag off" meta="The T21e grammar, drawn inside the frame the route has">
      <Row name="Insights" meaning="ff.insights is off; the route shows the state">
        <FramedBody title="Insights">
          <FlagOffState flag="ff.insights" label="Insights" icon="chart-column" />
        </FramedBody>
      </Row>
      <Row name="Attest" meaning="ff.attest is off">
        <FramedBody title="Audits">
          <FlagOffState flag="ff.attest" label="Attest" icon="shield-check" />
        </FramedBody>
      </Row>
      <Row name="From ViewState" meaning="The body takes { kind: flag-off }">
        <FramedBody title="Statements studio">
          <ViewStateBody
            state={{ kind: "flag-off", flag: "ff.statements_studio" }}
            flagLabel="Statements studio"
            empty={{ title: "No statements yet." }}
          />
        </FramedBody>
      </Row>
    </Sheet>
  );
}
