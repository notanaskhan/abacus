import type { CloseRowOut } from "@abacus/api-client";
import {
  ConfirmDialog,
  Count,
  DASH,
  DEFAULT_TZ,
  Icon,
  type IndexChip,
  type IndexColumn,
  IndexList,
  type IndexTile,
  type ListEnvelope,
  Menu,
  RegistryStatus,
  Spinner,
  Toast,
  Tooltip,
  ViewToggle,
  type ViewState,
  count,
  date,
  time,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { useSession } from "../../app-core/session";
import {
  CLOSE_PERIODS,
  type CloseFilters,
  DEFAULT_CLOSE_FILTERS,
  isClosePeriod,
  isCloseStatusFilter,
  isNarrowedCloses,
  useCloses,
  useRunningCloses,
} from "../../domain/closes";
import { COPY } from "./copy";

// CLS-01 · Closes index (C-01-T33; SPEC-655 AC-1 to AC-6; docs/screens/CLS-01.md). T1 over
// `GET /v1/closes` and `GET /v1/closes/running`: the split chips (Period, Status, Preparer,
// Reviewer, Attest), the four status tiles as filters (DV-9: Approved counts under In review,
// Locked under Delivered), the summary line, the rows with the reconciled bar, open issues, the
// due line (past due in firm business days, QC-7), the preparer and reviewer, and the running
// agent; the running pill at the bottom; a row's menu (Open · Start run · View plan) and Start
// run's confirm while statements are missing. Every figure is the server's (AC-2). The List ·
// Board toggle stays hidden while `board.enabled` is off. Each artboard is its data
// (fixtures/scenarios/CLS-01.ts):
//
//   a  Priya Raman at E0, 9:24 AM: 22 closes, tiles 3 · 11 · 5 · 3,
//      "22 closes · 51 open issues · 2 past due · 3 running"
//   b  the In progress tile pressed: 11 rows, "Showing 11 of 22"
//   c  Status │ Past due: Copperleaf and Bluebird Bakery
//   d  Attest │ Attest clients: "No attest clients this period"
//   e  the list never answers: skeleton tiles and rows
//   f  row hover on C11 with its "···" menu

export interface CLS01Props {
  filters: CloseFilters;
  onFilters: (next: CloseFilters) => void;
  /** Open a close's record (CLS-02). */
  onOpen?: (closeId: string) => void;
  /** Open CLS-02 with the run starting (the row menu's Start run, after its confirm). */
  onStartRun?: (closeId: string) => void;
  /** Open the client's close plan (CLS-09). */
  onViewPlan?: (row: CloseRowOut) => void;
  /** "+ New close…": ENG-03 with Monthly close preselected. */
  onNewClose?: () => void;
  /** "1099 / W-9 tracker ›" (CLS-13, planned). */
  onTracker?: () => void;
}

const TILES: readonly IndexTile[] = [
  { code: "not_started", label: "Not started", variant: "neutral" },
  { code: "in_progress", label: "In progress", variant: "state" },
  { code: "in_review", label: "In review", variant: "state" },
  { code: "delivered", label: "Delivered", variant: "green" },
];

const onDay = (day: string): string => `${day}T12:00:00Z`;

/** The 64×3 reconciled bar and its label (CLS-01 a): ink fill, olive at 100%. */
function Reconciled({ row }: { row: CloseRowOut }): JSX.Element {
  const full = row.accounts_total > 0 && row.accounts_reconciled === row.accounts_total;
  return (
    <span className="inline-flex items-center gap-[8px]" data-reconciled={row.reconciled_pct}>
      <span
        role="progressbar"
        aria-label={COPY.columns.reconciled}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={row.reconciled_pct}
        className="relative block h-[3px] w-[64px] overflow-hidden rounded-[2px] bg-chip"
      >
        <span
          className={`absolute top-0 left-0 block h-full ${full ? "bg-green" : "bg-espresso"}`}
          style={{ width: `${String(row.reconciled_pct)}%` }}
        />
      </span>
      <span className="text-dense tabular-nums">
        {COPY.reconciled(row.reconciled_pct, row.accounts_reconciled, row.accounts_total)}
      </span>
    </span>
  );
}

function Due({ row, now, tz }: { row: CloseRowOut; now: Date; tz: string }): JSX.Element {
  if (row.due_on == null) return <span className="text-ink-4">{DASH}</span>;
  const day = date(onDay(row.due_on), { tz, now });
  if (row.status === "delivered" || row.status === "locked") {
    return <span className="text-ink-2">{COPY.delivered(day)}</span>;
  }
  if (row.days_past_due != null) {
    return (
      <span data-past-due={row.days_past_due}>
        {day} · <span className="font-medium text-red-ink">{COPY.pastDue(row.days_past_due)}</span>
      </span>
    );
  }
  return <span>{day}</span>;
}

function Person({ row }: { row: CloseRowOut }): JSX.Element {
  const prep = row.preparer?.initials ?? DASH;
  const rev = row.reviewer?.initials ?? DASH;
  return (
    <abbr
      title={[row.preparer?.name, row.reviewer?.name].filter(Boolean).join(" / ")}
      className="text-dense text-ink-2 no-underline"
    >
      {prep} / {rev}
    </abbr>
  );
}

export function ClosesIndex({
  initial = {},
  ...rest
}: { initial?: Partial<CloseFilters> } & Omit<CLS01Props, "filters" | "onFilters">): JSX.Element {
  const [filters, setFilters] = useState<CloseFilters>(() => ({
    ...DEFAULT_CLOSE_FILTERS,
    ...initial,
  }));
  return <CLS01 filters={filters} onFilters={setFilters} {...rest} />;
}

export function CLS01({
  filters,
  onFilters,
  onOpen,
  onStartRun,
  onViewPlan,
  onNewClose,
  onTracker,
}: CLS01Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const board = useFlag("board.enabled") === true;
  const list = useCloses(filters);
  const running = useRunningCloses();
  const [confirm, setConfirm] = useState<CloseRowOut | null>(null);
  const narrowed = isNarrowedCloses(filters);
  const set = (patch: Partial<CloseFilters>): void => {
    onFilters({ ...filters, ...patch });
  };
  const clear = (): void => {
    onFilters({ ...DEFAULT_CLOSE_FILTERS, period: filters.period });
  };

  const page = list.data;
  let state: ViewState;
  if (list.isError) state = { kind: "error", retry: () => void list.refetch() };
  else if (page === undefined) state = { kind: "loading" };
  else if (page.items.length === 0 && !narrowed) state = { kind: "empty" };
  else if (page.items.length === 0 && filters.attest === true) {
    // CLS-01 d: the attest filter's own empty frame, with its icon, title and copy.
    state = { kind: "empty" };
  } else if (page.items.length === 0) {
    const q = filters.q.trim();
    state = {
      kind: "filtered-empty",
      ...(q === "" ? {} : { query: q, title: COPY.noMatch(q) }),
      clear,
    };
  } else state = { kind: "ready" };

  const total = page === undefined ? 0 : Object.values(page.tiles).reduce((n, v) => n + v, 0);
  const envelope: ListEnvelope<CloseRowOut> | undefined =
    page === undefined
      ? undefined
      : {
          items: page.items,
          next_cursor: page.next_cursor ?? null,
          total,
          counts: { ...page.tiles },
        };

  const people = new Map<string, string>();
  for (const r of page?.items ?? []) {
    if (r.preparer) people.set(r.preparer.user_id, r.preparer.name);
    if (r.reviewer) people.set(r.reviewer.user_id, r.reviewer.name);
  }
  const personOptions = [...people].map(([value, label]) => ({ value, label }));

  const chips: IndexChip[] = [
    {
      key: "period",
      label: COPY.chips.period,
      icon: "calendar",
      options: CLOSE_PERIODS.map((p) => ({ value: p, label: COPY.periods[p] })),
      value: filters.period,
      placeholder: COPY.periods[filters.period],
    },
    {
      key: "status",
      label: COPY.chips.status,
      icon: "circle-check",
      options: [
        ...TILES.map((t) => ({ value: t.code, label: t.label })),
        { value: "past_due", label: COPY.chips.pastDue },
      ],
      value: filters.status,
      placeholder: COPY.chips.all,
    },
    {
      key: "preparedBy",
      label: COPY.chips.preparer,
      icon: "circle-user-round",
      options: personOptions,
      value: filters.preparer,
      placeholder: COPY.chips.anyone,
    },
    {
      key: "reviewedBy",
      label: COPY.chips.reviewer,
      icon: "circle-user-round",
      options: personOptions,
      value: filters.reviewer,
      placeholder: COPY.chips.anyone,
    },
    {
      key: "attest",
      label: COPY.chips.attest,
      icon: "flag",
      options: [{ value: "true", label: COPY.chips.attestOnly }],
      value: filters.attest === null ? null : String(filters.attest),
      placeholder: COPY.chips.any,
    },
  ];

  const onChip = (key: string, value: string | null): void => {
    if (key === "period" && isClosePeriod(value)) set({ period: value });
    else if (key === "status") set({ status: isCloseStatusFilter(value) ? value : null });
    else if (key === "preparedBy") set({ preparer: value });
    else if (key === "reviewedBy") set({ reviewer: value });
    else if (key === "attest") set({ attest: value === "true" ? true : null });
  };

  const runs = new Map((running.data?.items ?? []).map((r) => [r.close_id, r]));

  const startRun = (row: CloseRowOut): void => {
    // AC-6: a close whose statements are not in yet asks first; no run starts without the click.
    if (row.status === "not_started") setConfirm(row);
    else onStartRun?.(row.close_id);
  };

  const columns: IndexColumn<CloseRowOut>[] = [
    {
      key: "client",
      header: COPY.columns.client,
      width: 300,
      cell: (r) => <span className="block truncate font-medium">{r.client_name}</span>,
    },
    {
      key: "period",
      header: COPY.columns.period,
      width: 96,
      cell: (r) => <span className="tabular-nums">{r.period}</span>,
    },
    {
      key: "status",
      header: COPY.columns.status,
      width: 128,
      cell: (r) => <RegistryStatus object="close" code={r.status} />,
    },
    {
      key: "reconciled",
      header: COPY.columns.reconciled,
      width: 210,
      cell: (r) => <Reconciled row={r} />,
    },
    {
      key: "openIssues",
      header: COPY.columns.openIssues,
      width: 96,
      align: "right",
      cell: (r) =>
        r.open_issues > 0 ? (
          <Count value={r.open_issues} tone="bad" />
        ) : (
          <span className="text-ink-4">{DASH}</span>
        ),
    },
    {
      key: "due",
      header: COPY.columns.due,
      width: 170,
      cell: (r) => <Due row={r} now={now} tz={tz} />,
    },
    {
      key: "prepRev",
      header: COPY.columns.prepRev,
      width: 96,
      cell: (r) => <Person row={r} />,
    },
    {
      key: "agent",
      header: COPY.columns.agent,
      cell: (r) => {
        const run = runs.get(r.close_id);
        const line = (
          <span className="inline-flex items-center gap-[6px] text-dense text-ink-2">
            <Spinner label={COPY.running} size={12} showLabel={false} />
            {COPY.running}
          </span>
        );
        if (!r.running) return null;
        return run === undefined ? (
          line
        ) : (
          <Tooltip
            content={COPY.runLine(run.run_no, run.done, run.total, time(run.started_at, { tz }))}
          >
            {line}
          </Tooltip>
        );
      },
    },
    {
      key: "menu",
      header: "",
      width: 56,
      align: "right",
      cell: (r) => (
        <span className="inline-flex items-center gap-[4px]" data-row-menu={r.close_id}>
          <Menu
            label={COPY.menu.label}
            trigger={
              <button
                type="button"
                aria-label={`${COPY.menu.label}: ${r.client_name}`}
                className="inline-flex size-[24px] items-center justify-center rounded-[6px] text-ink-3 hover:bg-nested"
              >
                <Icon name="ellipsis" size={14} />
              </button>
            }
            sections={[
              [
                { label: COPY.menu.open, onSelect: () => onOpen?.(r.close_id) },
                {
                  label: COPY.menu.startRun,
                  disabled: !r.allowed_actions?.includes("close_run.start"),
                  onSelect: () => {
                    startRun(r);
                  },
                },
                { label: COPY.menu.viewPlan, onSelect: () => onViewPlan?.(r) },
              ],
            ]}
          />
          <Icon name="chevron-right" size={12} className="text-ink-3" />
        </span>
      ),
    },
  ];

  const summaryText =
    page === undefined
      ? undefined
      : COPY.summary(
          count(total),
          count(page.summary.open_issues),
          count(page.summary.past_due),
          count(page.summary.running),
        );
  const tile = filters.status !== null && filters.status !== "past_due" ? filters.status : null;
  const runningCount = running.data?.items.length ?? 0;

  return (
    <div className="relative flex min-h-0 flex-1 flex-col" data-screen="CLS-01">
      <IndexList<CloseRowOut>
        title={COPY.title}
        noun={COPY.noun}
        state={state}
        envelope={envelope}
        columns={columns}
        rowKey={(r) => r.close_id}
        {...(onOpen === undefined
          ? {}
          : {
              onOpen: (r: CloseRowOut) => {
                onOpen(r.close_id);
              },
            })}
        chips={chips}
        onChip={onChip}
        tiles={TILES}
        tile={tile}
        onTile={(code) => {
          set({ status: isCloseStatusFilter(code) ? code : null });
        }}
        {...(summaryText === undefined ? {} : { summary: summaryText })}
        onClear={clear}
        query={filters.q}
        onQuery={(q) => {
          set({ q });
        }}
        searchPlaceholder={COPY.search}
        {...(onNewClose === undefined ? {} : { newLabel: COPY.newClose, onNew: onNewClose })}
        barEnd={
          <button
            type="button"
            onClick={onTracker}
            disabled={onTracker === undefined}
            className="text-dense text-ink-2 hover:text-ink disabled:cursor-default"
          >
            {COPY.tracker} ›
          </button>
        }
        {...(board
          ? {
              actions: (
                <ViewToggle
                  view="list"
                  views={[
                    { v: "list", label: COPY.view.list, icon: "list" },
                    { v: "board", label: COPY.view.board, icon: "layout-grid" },
                  ]}
                />
              ),
            }
          : {})}
        empty={
          filters.attest === true
            ? { icon: "flag", title: COPY.attestEmpty.title, body: COPY.attestEmpty.body }
            : { icon: "calendar", title: COPY.empty.title, body: COPY.empty.body }
        }
      />
      {runningCount > 0 && (
        <div className="pointer-events-none absolute right-0 bottom-[24px] left-0 flex justify-center">
          <div className="pointer-events-auto" data-running-pill={runningCount}>
            <Toast kind="running" text={COPY.runningPill(runningCount)} />
          </div>
        </div>
      )}
      {confirm !== null && (
        <ConfirmDialog
          open
          onOpenChange={(open) => {
            if (!open) setConfirm(null);
          }}
          title={COPY.startConfirm.title}
          confirmLabel={COPY.startConfirm.confirm}
          cancelLabel={COPY.startConfirm.cancel}
          destructive={false}
          onConfirm={() => {
            const id = confirm.close_id;
            setConfirm(null);
            onStartRun?.(id);
          }}
        >
          {COPY.startConfirm.body}
        </ConfirmDialog>
      )}
    </div>
  );
}
