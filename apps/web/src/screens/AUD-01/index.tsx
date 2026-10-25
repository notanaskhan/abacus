import type {
  AuditIndexPage,
  AuditIndexRowOut,
  AuditIndexSummaryOut,
  AuditRunBadgeOut,
} from "@abacus/api-client";
import {
  Button,
  DASH,
  DEFAULT_TZ,
  Icon,
  type IndexChip,
  type IndexColumn,
  IndexList,
  type IndexTile,
  type ListEnvelope,
  Pill,
  Segmented,
  type StatusTileVariant,
  Tag,
  Tooltip,
  type ViewState,
  count,
  date,
  isoDate,
  status,
  time,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  AUDIT_DUE_WINDOWS,
  AUDIT_SEGMENTS,
  AUDIT_TILES,
  type AuditFilters,
  type AuditSearch,
  type AuditSegment,
  auditFiltersOf,
  auditSearchOf,
  DEFAULT_AUDIT_FILTERS,
  auditTypeLabel,
  auditTypeWord,
  isAuditDue,
  isAuditSegment,
  isAuditTile,
  isNarrowedAudits,
  useAuditIndex,
} from "../../domain/audits";
import { COPY } from "./copy";

// AUD-01 · Audits index (A-01-T11; docs/screens/AUD-01.md). T1 over `GET /v1/audits` with the R2
// 44 px tabs bar: the segments (a tablist with counts from `facets.segment`; SOC & IT and Internal
// audit carry no badge while the firm lacks their entitlement), the split chips, the five phase
// tiles (the server's `counts`, minus the pressed tile) with the type caption, and the ledger rows
// grouped by phase. Each artboard is its data (fixtures/scenarios/AUD-01.ts):
//
//   a  Hannah Leclerc at E0, 9:41 AM: 27 audits, tiles 7 · 9 · 6 · 2 · 3
//   b  the Ready to release tile pressed: Cobalt Ridge and Halden Health, "Showing 2 of 27"
//   c  Report due │ Next 14 days: Sep 18, 21, 25, 28
//   d  Northwind's run: "Processing" with its popover open on focus or hover
//   e  "Pinecrest" matches nothing: "No results for 'Pinecrest'." and Clear filters
//   f  the list never answers: skeleton tile counts and 8 skeleton rows
//   g  the wave-7 view at 10:30 AM (E2): 33 rows, SOC & IT and Internal audit segments
//   h  g with SOC & IT on: Tessellate, Larkfield, Brightline
//
// i (Board) is deferred to K-04: no ViewToggle renders until C14 registers. Every outbound target
// but AUD-02 (AUD-03, ENG-03, AUD-25, ATT-01, IAU-01) is planned: the PBC cell and the archive
// pill are plain, "+ New audit" is drawn disabled with its hint outside production.

export interface AUD01Props {
  filters: AuditFilters;
  onFilters: (next: AuditFilters) => void;
  /** Open an audit's cockpit (AUD-02) at Source Documents. */
  onOpen?: (workItemId: string) => void;
}

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

const DAY_MS = 86_400_000;

/** Whole calendar days from today (in the firm's zone) to `on`. */
export function daysTo(on: string, now: Date, tz: string): number {
  const today = isoDate(now, tz);
  return Math.round((Date.parse(`${on}T12:00:00Z`) - Date.parse(`${today}T12:00:00Z`)) / DAY_MS);
}

const DUE_TONE: Readonly<Record<NonNullable<AuditIndexRowOut["report_due_tone"]>, string>> = {
  past_due: "text-red-ink font-medium",
  within_7_days: "text-red-ink font-medium",
  within_30_days: "text-amber-ink",
  later: "text-ink-2",
};

function tileVariant(v: string | null | undefined): StatusTileVariant {
  return v === "neutral" ||
    v === "state" ||
    v === "green-tint" ||
    v === "green" ||
    v === "muted" ||
    v === "soon"
    ? v
    : "neutral";
}

/** The run summary in words (C6 v1; DV-11). */
export function runWords(run: AuditRunBadgeOut, tz: string): { head: string; detail: string } {
  const head = COPY.run.head(
    String(run.run_number),
    time(run.started_at, { tz }),
    run.started_by_name,
  );
  const progress = COPY.run.progress(
    String(run.workpapers_complete),
    String(run.workpapers_total),
  );
  return {
    head,
    detail:
      run.blocked_on_role == null
        ? progress
        : `${progress} · ${COPY.run.blocked(run.blocked_on_role)}`,
  };
}

function PhaseCell({
  row,
  now,
  tz,
}: {
  row: AuditIndexRowOut;
  now: Date;
  tz: string;
}): JSX.Element {
  let pill: JSX.Element;
  if (row.run_badge != null) {
    const words = runWords(row.run_badge, tz);
    const processing = status("audit_engagement", "processing");
    pill = (
      <Tooltip content={words.head} detail={words.detail}>
        <button
          type="button"
          data-phase="processing"
          className="inline-flex rounded-pill focus-visible:outline-offset-2"
        >
          <Pill variant={processing.variant ?? "amber"} size="state" spin>
            {processing.label}
          </Pill>
        </button>
      </Tooltip>
    );
  } else {
    const word =
      row.phase === "released" && row.released_on != null
        ? status("audit_engagement", "released", {
            vars: { date: date(onDay(row.released_on), { now, tz }) },
          })
        : status("audit_engagement", row.phase);
    pill = (
      <Pill data-phase={row.phase} variant={word.variant ?? "amber"} size="state">
        {word.label}
      </Pill>
    );
  }
  return (
    <span className="flex min-w-0 items-center gap-[6px]">
      {pill}
      {(row.tags ?? []).map((t) => (
        <Tag key={`${t.source}:${t.code}`} className="min-w-0 truncate">
          {t.text}
        </Tag>
      ))}
    </span>
  );
}

function PbcCell({ row }: { row: AuditIndexRowOut }): JSX.Element {
  const pbc = row.pbc;
  if (pbc == null) return <span className="text-ink-4">{DASH}</span>;
  const pct = pbc.total === 0 ? 0 : Math.round((pbc.received / pbc.total) * 100);
  const text = COPY.pbc(count(pbc.received), count(pbc.total));
  return (
    <span className="inline-flex flex-col items-end gap-[3px]">
      <span className="text-dense tabular-nums">{text}</span>
      <span
        role="progressbar"
        aria-label={text}
        aria-valuenow={pbc.received}
        aria-valuemin={0}
        aria-valuemax={pbc.total}
        className="relative block h-[3px] w-[40px] overflow-hidden rounded-[2px] bg-chip"
      >
        <span
          className="block h-full rounded-[2px] bg-espresso"
          style={{ width: `${String(pct)}%` }}
        />
      </span>
    </span>
  );
}

function DueCell({ row, now, tz }: { row: AuditIndexRowOut; now: Date; tz: string }): JSX.Element {
  const on = row.report_due_on;
  if (on == null) return <span className="text-ink-4">{DASH}</span>;
  const tone = row.report_due_tone ?? "later";
  return (
    <span data-due={tone} className={DUE_TONE[tone]}>
      {date(onDay(on), { now, tz })}
      <span className="sr-only">{` ${COPY.dueIn(daysTo(on, now, tz))}`}</span>
    </span>
  );
}

function ArchiveCell({ row }: { row: AuditIndexRowOut }): JSX.Element {
  const archive = row.archive;
  if (archive == null) return <span className="text-ink-4">{DASH}</span>;
  if (archive.state === "archiving") {
    const word = status("audit_engagement", "archiving", {
      vars: { days: String(archive.days_left ?? 0) },
    });
    return (
      <Pill data-archive="archiving" variant={word.variant ?? "muted"} size="state">
        <Icon name="clock" size={12} />
        {word.label}
      </Pill>
    );
  }
  const word = status("audit_engagement", "archived");
  const pill = (
    <Pill data-archive="archived" variant={word.variant ?? "soon"} size="state">
      <Icon name="lock" size={12} />
      {word.label}
    </Pill>
  );
  return archive.firm_tool_ref == null ? (
    pill
  ) : (
    <Tooltip content={COPY.archiveTooltip(archive.firm_tool_ref)}>
      <span tabIndex={0} className="inline-flex rounded-pill">
        {pill}
      </span>
    </Tooltip>
  );
}

function captionOf(summary: AuditIndexSummaryOut, total: number, entitled: ReadonlySet<string>) {
  return COPY.caption({
    total: count(total),
    ebp: count(summary.ebp),
    fs: count(summary.fs_audit),
    review: count(summary.review),
    compilation: count(summary.compilation_preparation),
    ...(entitled.has("soc") ? { soc: count(summary.soc ?? 0) } : {}),
    ...(entitled.has("ia") ? { ia: count(summary.internal_audit ?? 0) } : {}),
  });
}

/** The routed page: the filters live in the URL (A-01 Story 1.2). */
export function AuditsSearchPage({
  search,
  onSearch,
  onOpen,
}: {
  search: Readonly<Record<string, unknown>>;
  onSearch: (next: AuditSearch) => void;
  onOpen?: (workItemId: string) => void;
}): JSX.Element {
  return (
    <AUD01
      filters={auditFiltersOf(search)}
      onFilters={(next) => {
        onSearch(auditSearchOf(next));
      }}
      {...(onOpen === undefined ? {} : { onOpen })}
    />
  );
}

/** The screen with its own filters: the gallery's artboard. */
export function AuditsIndex({
  initial = {},
  onOpen,
}: {
  initial?: Partial<AuditFilters>;
  onOpen?: (workItemId: string) => void;
}): JSX.Element {
  const [filters, setFilters] = useState<AuditFilters>(() => ({
    ...DEFAULT_AUDIT_FILTERS,
    ...initial,
  }));
  return (
    <AUD01
      filters={filters}
      onFilters={setFilters}
      {...(onOpen === undefined ? {} : { onOpen })}
    />
  );
}

export function AUD01({ filters, onFilters, onOpen }: AUD01Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const list = useAuditIndex(filters);
  const canCreate = useCan("engagement.create");

  const pages: AuditIndexPage[] = list.data?.pages ?? [];
  const first = pages[0];
  const last = pages[pages.length - 1];
  const items = pages.flatMap((p) => p.items);
  const narrowed = isNarrowedAudits(filters) || filters.segment !== null;
  const set = (patch: Partial<AuditFilters>): void => {
    onFilters({ ...filters, ...patch });
  };
  // Clear filters resets every filter and the segment (A-01 Story 1.2).
  const clear = (): void => {
    onFilters({ ...DEFAULT_AUDIT_FILTERS });
  };

  let state: ViewState;
  if (list.isError) state = { kind: "error", retry: () => void list.refetch() };
  else if (first === undefined) state = { kind: "loading" };
  else if (first.total === 0 && !narrowed) state = { kind: "empty" };
  else if (items.length === 0) {
    const q = filters.q.trim();
    state = {
      kind: "filtered-empty",
      ...(q === "" ? {} : { query: q, title: COPY.noMatch(q) }),
      clear,
    };
  } else state = { kind: "ready" };

  const envelope: ListEnvelope<AuditIndexRowOut> | undefined =
    first === undefined
      ? undefined
      : {
          items,
          next_cursor: last?.next_cursor ?? null,
          total: first.total,
          counts: first.counts ?? {},
          facets: first.facets ?? {},
        };

  // The segments are the server's facets; a segment the firm is not entitled to has none and
  // renders without a badge (revision item 1). "All" is their sum.
  const segmentFacets = first?.facets?.segment ?? [];
  const entitled = new Set(segmentFacets.map((f) => f.value));
  const segmentCount = (s: AuditSegment): number | undefined =>
    segmentFacets.find((f) => f.value === s)?.n;
  const allCount = segmentFacets.reduce((sum, f) => sum + f.n, 0);
  const tabs = (
    <Segmented
      label={COPY.segmentsLabel}
      options={[
        { label: COPY.segments.all, ...(first === undefined ? {} : { count: allCount }) },
        ...AUDIT_SEGMENTS.map((s) => {
          const n = segmentCount(s);
          return { label: COPY.segments[s], ...(n === undefined ? {} : { count: n }) };
        }),
      ]}
      active={filters.segment === null ? COPY.segments.all : COPY.segments[filters.segment]}
      onChange={(label) => {
        const segment = AUDIT_SEGMENTS.find((s) => COPY.segments[s] === label) ?? null;
        set({ segment: isAuditSegment(segment) ? segment : null });
      }}
    />
  );

  const tileWords = AUDIT_TILES.map((code) => ({ code, word: status("audit_engagement", code) }));
  const phaseLabel = (code: string): string => (isAuditTile(code) ? COPY.tiles[code] : code);

  const chips: IndexChip[] = [
    {
      key: "type",
      label: COPY.chips.type,
      icon: "layers",
      options: (first?.facets?.type ?? []).map((f) => ({
        value: f.value,
        label: auditTypeWord(f.value),
      })),
      value: filters.type,
      placeholder: COPY.chips.all,
    },
    {
      key: "phase",
      label: COPY.chips.phase,
      icon: "circle-dot",
      options: AUDIT_TILES.map((code) => ({ value: code, label: phaseLabel(code) })),
      value: filters.phase,
      placeholder: COPY.chips.all,
    },
    {
      key: "partner",
      label: COPY.chips.partner,
      icon: "circle-user-round",
      options: (first?.facets?.partner ?? []).map((f) => ({ value: f.value, label: f.label })),
      value: filters.partner,
      placeholder: COPY.chips.all,
    },
    {
      key: "office",
      label: COPY.chips.office,
      icon: "map-pin",
      options: officeOptions(items),
      value: filters.office,
      placeholder: COPY.chips.allOffices,
    },
    {
      key: "due",
      label: COPY.chips.due,
      icon: "calendar",
      options: AUDIT_DUE_WINDOWS.map((w) => ({ value: w, label: COPY.due[w] })),
      value: filters.due,
      placeholder: COPY.chips.any,
    },
    {
      key: "period",
      label: COPY.chips.period,
      align: "end",
      options: (first?.facets?.period ?? []).map((f) => ({ value: f.value, label: f.label })),
      value: filters.period,
      placeholder: COPY.chips.periods,
    },
  ];

  const onChip = (key: string, value: string | null): void => {
    if (key === "type") {
      const t = (first?.facets?.type ?? []).find((f) => f.value === value)?.value ?? null;
      set({ type: t as AuditFilters["type"] });
    } else if (key === "phase") set({ phase: isAuditTile(value) ? value : null });
    else if (key === "partner") set({ partner: value });
    else if (key === "office") set({ office: value });
    else if (key === "due") set({ due: isAuditDue(value) ? value : null });
    else if (key === "period") set({ period: value });
  };

  const tiles: IndexTile[] = tileWords.map(({ code, word }) => ({
    code,
    label: phaseLabel(code),
    variant: tileVariant(word.variant),
  }));

  // The tiles count every filter but the pressed tile, so their sum is the list without it:
  // "Showing 2 of 27" with Ready to release pressed (AUD-01 b).
  const tileSum = AUDIT_TILES.reduce((sum, code) => sum + (first?.counts?.[code] ?? 0), 0);
  const caption = first === undefined ? undefined : captionOf(first.summary, tileSum, entitled);
  const countText =
    first === undefined ? undefined : COPY.showing(count(items.length), count(tileSum));

  const columns: IndexColumn<AuditIndexRowOut>[] = [
    {
      key: "engagement",
      header: COPY.columns.engagement,
      width: 290,
      cell: (r) => <span className="block truncate">{r.name}</span>,
    },
    {
      key: "type",
      header: COPY.columns.type,
      width: 170,
      cell: (r) => <span className="block truncate text-ink-2">{auditTypeLabel(r)}</span>,
    },
    {
      key: "period",
      header: COPY.columns.period,
      width: 110,
      cell: (r) => <span className="block truncate text-ink-2">{r.period_label ?? DASH}</span>,
    },
    {
      key: "phase",
      header: COPY.columns.phase,
      width: 200,
      cell: (r) => <PhaseCell row={r} now={now} tz={tz} />,
    },
    {
      key: "pbc",
      header: COPY.columns.pbc,
      width: 90,
      align: "right",
      cell: (r) => <PbcCell row={r} />,
    },
    {
      key: "epMgr",
      header: COPY.columns.epMgr,
      width: 84,
      cell: (r) => (
        <span className="text-ink-2">
          {r.partner_initials == null && r.manager_initials == null
            ? DASH
            : `${r.partner_initials ?? DASH} / ${r.manager_initials ?? DASH}`}
        </span>
      ),
    },
    {
      key: "office",
      header: COPY.columns.office,
      width: 92,
      cell: (r) => <span className="text-ink-2">{r.office_name ?? DASH}</span>,
    },
    {
      key: "due",
      header: COPY.columns.due,
      width: 96,
      align: "right",
      cell: (r) => <DueCell row={r} now={now} tz={tz} />,
    },
    {
      key: "archive",
      header: COPY.columns.archive,
      width: 150,
      cell: (r) => <ArchiveCell row={r} />,
    },
  ];

  // Rows group by tile ("PLANNING · 7"); an archived row reads Released (DEC-263).
  const groupCount = new Map<string, number>();
  for (const r of items) {
    const g = groupKey(r);
    groupCount.set(g, (groupCount.get(g) ?? 0) + 1);
  }
  const groupOf = (r: AuditIndexRowOut) => {
    const g = groupKey(r);
    return { key: g, label: COPY.group(phaseLabel(g), count(groupCount.get(g) ?? 0)) };
  };

  // ENG-03 is planned: "+ New audit" is drawn for `engagement.create` holders, disabled with its
  // hint, and not at all in production (docs/screens/AUD-01.md, Links).
  const newButton =
    canCreate && PLANNED_VISIBLE ? (
      <Button variant="primary" icon="plus" disabled title={COPY.newAuditHint}>
        {COPY.newAudit}
      </Button>
    ) : undefined;

  return (
    <div data-screen="AUD-01" className="flex min-h-0 flex-1 flex-col">
      <IndexList<AuditIndexRowOut>
        title={COPY.title}
        noun={COPY.noun}
        state={state}
        envelope={envelope}
        columns={columns}
        rowKey={(r) => r.work_item_id}
        groupOf={groupOf}
        {...(onOpen === undefined
          ? {}
          : {
              onOpen: (r: AuditIndexRowOut) => {
                onOpen(r.work_item_id);
              },
              onSelect: (r: AuditIndexRowOut) => {
                onOpen(r.work_item_id);
              },
            })}
        tabs={tabs}
        chips={chips}
        onChip={onChip}
        tiles={tiles}
        tile={filters.phase}
        onTile={(code) => {
          set({ phase: isAuditTile(code) ? code : null });
        }}
        {...(caption === undefined ? {} : { summary: caption })}
        {...(isNarrowedAudits(filters) ? { onClear: clear } : {})}
        query={filters.q}
        searchPlaceholder={COPY.search}
        onQuery={(q) => {
          set({ q });
        }}
        {...(countText === undefined ? {} : { countText })}
        {...(newButton === undefined ? {} : { actions: newButton })}
        {...(list.hasNextPage
          ? {
              footer: (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={list.isFetchingNextPage}
                  onClick={() => void list.fetchNextPage()}
                >
                  {COPY.loadMore}
                </Button>
              ),
            }
          : {})}
        empty={{ icon: "briefcase", title: COPY.empty }}
      />
    </div>
  );
}

function groupKey(r: AuditIndexRowOut): string {
  return r.phase === "archived" || r.phase === "archiving" ? "released" : r.phase;
}

function officeOptions(rows: readonly AuditIndexRowOut[]) {
  const seen = new Map<string, string>();
  for (const r of rows) {
    if (r.office_id != null && r.office_name != null) seen.set(r.office_id, r.office_name);
  }
  return [...seen].map(([value, label]) => ({ value, label }));
}
