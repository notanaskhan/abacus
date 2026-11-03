import type { NoticeRowOut } from "@abacus/api-client";
import {
  AgentMonogram,
  DASH,
  DEFAULT_TZ,
  GroupedTile,
  Icon,
  type IndexChip,
  type IndexColumn,
  IndexList,
  type IndexTile,
  type ListEnvelope,
  RegistryStatus,
  Tooltip,
  type ViewState,
  amount,
  count,
  date,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  DEFAULT_NOTICE_FILTERS,
  NOTICE_AGENCIES,
  NOTICE_TYPES,
  type NoticeFilters,
  isNarrowedNotices,
  isNoticeAgency,
  isNoticeTile,
  isNoticeType,
  useNotices,
  useNoticesSummary,
} from "../../domain/notices";
import { COPY } from "./copy";

// NOT-01 · Notices index (N-04-T05; docs/screens/NOT-01.md). T1 over `GET /v1/notices` and
// `GET /v1/notices/summary`: the split chips (Agency, Notice, Assignee, Respond by), the agent chip
// at the bar's end (the firm's agent stage; its WB-06 target is planned), the four status tiles as
// filters (the server's `counts`, minus the pressed tile), the grouped type tile and the summary
// line, and the rows by deadline risk. Respond-by within 7 days reads red with its days, within 30
// amber; sent rows read "Response sent {day}". Each artboard is its data
// (fixtures/scenarios/NOT-01.ts):
//
//   a  Kevin Osei at E0, 9:24 AM: nine notices, tiles 2 · 3 · 2 · 2, 3 CP2000 · 2 CP14 · 1 CP501 ·
//      3 State, "9 open · 1 due within 7 days · 1 blocked (no authorization)"
//   e  the New tile pressed: N5 and N9, and Clear
//   f  none visible: "No open notices."
//   g  the list never answers: skeleton tile counts and rows
//
// b, c and d (the O3 intake sheet) are N-04-T09; "+ Add notice" waits for it and is drawn disabled
// outside production. A row opens NOT-02 (N-04-T14) through `onOpen`.

export interface NOT01Props {
  filters: NoticeFilters;
  onFilters: (next: NoticeFilters) => void;
  /** Open a notice's workspace (NOT-02). */
  onOpen?: (noticeId: string) => void;
}

const TILES: readonly IndexTile[] = [
  { code: "new", label: "New", variant: "red-tint" },
  { code: "analyzing", label: "Analyzing", variant: "state" },
  { code: "response_drafted", label: "Response drafted", variant: "state" },
  { code: "awaiting", label: "Awaiting IRS", variant: "muted" },
];

const RISK_TONE: Readonly<Record<NoticeRowOut["risk"], string>> = {
  red: "text-red-ink font-medium",
  amber: "text-amber-ink",
  none: "text-ink-2",
};

const onDay = (day: string): string => `${day}T12:00:00Z`;

function money(v: string | null | undefined): string {
  return v == null ? DASH : amount(v).text;
}

/** "$686.40 + $66.61 interest", "$1,980.00 · disagreed", "$3,412.18". */
export function amountText(row: NoticeRowOut): string {
  const a = row.amounts;
  if (a.interest != null && a.tax != null)
    return `${money(a.tax)} ${COPY.interest(money(a.interest))}`;
  const base = money(a.total ?? a.tax);
  return row.position === "disagree" ? `${base} · ${COPY.disagreed}` : base;
}

function RespondBy({ row, now, tz }: { row: NoticeRowOut; now: Date; tz: string }): JSX.Element {
  if (row.respond_by == null) {
    return (
      <span className="text-ink-2">
        {row.sent_on == null ? DASH : COPY.sent(date(onDay(row.sent_on), { tz, now }))}
      </span>
    );
  }
  const day = date(onDay(row.respond_by), { tz, now });
  const days = row.respond_by_days;
  return (
    <span className={RISK_TONE[row.risk]} data-risk={row.risk}>
      {days == null || row.risk === "none" ? day : `${day} · ${COPY.days(days)}`}
    </span>
  );
}

function Authorization({ row }: { row: NoticeRowOut }): JSX.Element {
  if (!row.authorization.on_file) {
    return (
      <span className="inline-flex items-center rounded-pill bg-red-tint px-[8px] text-meta text-red-ink">
        {row.authorization.label}
      </span>
    );
  }
  // "8821 ✓": the label without its check, and the 12 px olive check.
  const label = row.authorization.label.replace(/\s*✓$/, "");
  return (
    <span className="inline-flex items-center gap-[4px] text-dense text-ink-2">
      {label}
      <Icon name="check" size={12} className="text-green-ink" />
    </span>
  );
}

function AgentChip({ stage }: { stage: keyof typeof COPY.agent.stage }): JSX.Element {
  const chip = (
    <span
      data-agent-chip={stage}
      className="inline-flex h-[29px] items-center gap-[6px] rounded-pill bg-card px-[10px] text-dense text-ink-2 shadow-e1"
    >
      <AgentMonogram size={14} label={COPY.agent.name} />
      <span>
        {COPY.agent.name} · {COPY.agent.onArrival} · {COPY.agent.stage[stage]}
      </span>
      {PLANNED_VISIBLE && <Icon name="chevron-right" size={12} />}
    </span>
  );
  // WB-06 is planned (W-03): the chip is plain text in production (deviation 1).
  return PLANNED_VISIBLE ? <Tooltip content="WB-06">{chip}</Tooltip> : chip;
}

export function NoticesIndex({
  initial = {},
  onOpen,
}: {
  initial?: Partial<NoticeFilters>;
  onOpen?: (noticeId: string) => void;
}): JSX.Element {
  const [filters, setFilters] = useState<NoticeFilters>(() => ({
    ...DEFAULT_NOTICE_FILTERS,
    ...initial,
  }));
  return (
    <NOT01
      filters={filters}
      onFilters={setFilters}
      {...(onOpen === undefined ? {} : { onOpen })}
    />
  );
}

export function NOT01({ filters, onFilters, onOpen }: NOT01Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const list = useNotices(filters);
  const summary = useNoticesSummary();
  const canAdd = useCan("notice_intake.create");
  const narrowed = isNarrowedNotices(filters);
  const set = (patch: Partial<NoticeFilters>): void => {
    onFilters({ ...filters, ...patch });
  };
  const clear = (): void => {
    onFilters(DEFAULT_NOTICE_FILTERS);
  };

  const page = list.data;
  const facts = summary.data;
  let state: ViewState;
  if (list.isError) state = { kind: "error", retry: () => void list.refetch() };
  else if (page === undefined) state = { kind: "loading" };
  else if (page.total === 0 && !narrowed) state = { kind: "empty" };
  else if (page.items.length === 0) {
    const q = filters.q.trim();
    state = {
      kind: "filtered-empty",
      ...(q === "" ? {} : { query: q, title: COPY.noMatch(q) }),
      clear,
    };
  } else state = { kind: "ready" };

  const envelope: ListEnvelope<NoticeRowOut> | undefined =
    page === undefined
      ? undefined
      : {
          items: page.items,
          next_cursor: page.next_cursor ?? null,
          total: page.total,
          counts: page.counts ?? {},
          ...(page.facets === undefined ? {} : { facets: page.facets }),
        };

  const chips: IndexChip[] = [
    {
      key: "agency",
      label: COPY.chips.agency,
      icon: "landmark",
      options: NOTICE_AGENCIES.map((a) => ({ value: a, label: COPY.agencies[a] })),
      value: filters.agency,
      placeholder: COPY.chips.all,
    },
    {
      key: "type",
      label: COPY.chips.notice,
      icon: "file-text",
      options: NOTICE_TYPES.map((t) => ({ value: t, label: COPY.types[t] })),
      value: filters.type,
      placeholder: COPY.chips.all,
    },
    {
      key: "assignee",
      label: COPY.chips.assignee,
      icon: "circle-user-round",
      options: (page?.facets?.assignee ?? []).map((f) => ({ value: f.value, label: f.label })),
      value: filters.assignee,
      placeholder: COPY.chips.anyone,
    },
    {
      key: "respondBy",
      label: COPY.chips.respondBy,
      icon: "calendar",
      options: ([7, 30] as const).map((d) => ({ value: String(d), label: COPY.windows[d] })),
      value: filters.respondBy === null ? null : String(filters.respondBy),
      placeholder: COPY.chips.any,
    },
  ];

  const onChip = (key: string, value: string | null): void => {
    if (key === "agency") set({ agency: isNoticeAgency(value) ? value : null });
    else if (key === "type") set({ type: isNoticeType(value) ? value : null });
    else if (key === "assignee") set({ assignee: value });
    else if (key === "respondBy")
      set({ respondBy: value === "7" ? 7 : value === "30" ? 30 : null });
  };

  const columns: IndexColumn<NoticeRowOut>[] = [
    {
      key: "client",
      header: COPY.columns.client,
      cell: (r) => (
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-medium">{r.client_name}</span>
          {r.form_line != null && <span className="text-meta text-ink-3">{r.form_line}</span>}
        </span>
      ),
    },
    {
      key: "agency",
      header: COPY.columns.agency,
      width: 120,
      cell: (r) => <span className="text-ink-2">{r.agency_name}</span>,
    },
    {
      key: "notice",
      header: COPY.columns.notice,
      width: 200,
      cell: (r) => (
        <span className="block truncate">
          {r.notice_code} · {r.title}
        </span>
      ),
    },
    {
      key: "taxYear",
      header: COPY.columns.taxYear,
      width: 70,
      cell: (r) => String(r.tax_year),
    },
    {
      key: "received",
      header: COPY.columns.received,
      width: 90,
      cell: (r) => <span className="text-ink-2">{date(onDay(r.received_on), { tz, now })}</span>,
    },
    {
      key: "respondBy",
      header: COPY.columns.respondBy,
      width: 130,
      align: "right",
      cell: (r) => <RespondBy row={r} now={now} tz={tz} />,
    },
    {
      key: "amount",
      header: COPY.columns.amount,
      width: 150,
      align: "right",
      cell: (r) => <span className="tabular-nums">{amountText(r)}</span>,
    },
    {
      key: "status",
      header: COPY.columns.status,
      width: 150,
      cell: (r) => (
        <RegistryStatus
          object="notice"
          code={r.status}
          {...(r.agency === "state" && r.status === "awaiting_irs"
            ? { context: "state_agency" }
            : {})}
        />
      ),
    },
    {
      key: "assignee",
      header: COPY.columns.assignee,
      width: 70,
      cell: (r) =>
        r.assignee === null ? (
          <span className="text-ink-4">{DASH}</span>
        ) : (
          <abbr title={r.assignee.name} className="text-dense text-ink-2 no-underline">
            {r.assignee.initials}
          </abbr>
        ),
    },
    {
      key: "authorization",
      header: COPY.columns.authorization,
      width: 130,
      cell: (r) => <Authorization row={r} />,
    },
  ];

  const summaryText =
    facts === undefined
      ? undefined
      : COPY.summary(count(facts.open), count(facts.due_within_7), count(facts.blocked));

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-screen="NOT-01">
      <IndexList<NoticeRowOut>
        title={COPY.title}
        noun={COPY.noun}
        state={state}
        envelope={envelope}
        columns={columns}
        rowKey={(r) => r.id}
        twoLine={(r) => r.form_line != null}
        {...(onOpen === undefined
          ? {}
          : {
              onOpen: (r: NoticeRowOut) => {
                onOpen(r.id);
              },
            })}
        chips={chips}
        onChip={onChip}
        tiles={TILES}
        tile={filters.tile}
        onTile={(code) => {
          set({ tile: isNoticeTile(code) ? code : null });
        }}
        tilesAfter={
          <GroupedTile
            title={COPY.byType}
            pending={facts === undefined}
            items={(facts?.by_type ?? []).map((t) => ({
              key: t.key,
              label: t.label,
              count: t.count,
            }))}
          />
        }
        {...(summaryText === undefined ? {} : { summary: summaryText })}
        onClear={clear}
        query={filters.q}
        onQuery={(q) => {
          set({ q });
        }}
        searchPlaceholder={COPY.search}
        {...(canAdd && PLANNED_VISIBLE
          ? { newLabel: COPY.addNotice, onNew: () => undefined }
          : {})}
        {...(facts === undefined ? {} : { barEnd: <AgentChip stage={facts.agent_stage} /> })}
        empty={{ icon: "file-text", title: COPY.empty.title, body: COPY.empty.body }}
      />
    </div>
  );
}
