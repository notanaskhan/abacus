import type {
  EngagementIndexPage,
  EngagementIndexRowOut,
  EngagementLetterSummaryOut,
  EngagementStatus,
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
  type RegistryObject,
  Segmented,
  StatusPill,
  type StatusTileVariant,
  SubLine,
  type ViewState,
  cn,
  count,
  date,
  isoDate,
  status,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { useStaff } from "../../domain/clients";
import {
  DEFAULT_ENGAGEMENT_FILTERS,
  ENGAGEMENT_LINES,
  ENGAGEMENT_TILES,
  type EngagementFilters,
  type EngagementLine,
  isEngagementLine,
  isEngagementTile,
  isNarrowedIndex,
  useEngagementIndex,
} from "../../domain/engagements";
import { COPY } from "./copy";

// ENG-01 · Engagements index (P-07-T27; docs/screens/ENG-01.md). T1 over `GET /v1/engagements/
// index`: the service-line Segmented, the split chips (Office, Partner, Letter, Next due; Period at
// the right end), the seven status tiles that filter and foot (the server's `counts`, minus the
// selected tile) with the summary line, and the ledger rows past due first. Each artboard is its
// data (fixtures/scenarios/ENG-01.ts):
//
//   a  Margaret Okonkwo, every line, Period │ Current: 273 engagements (DEC-343), the first 16 rows
//   b  Letter │ Not signed with the Accepted tile: rows 4, 6, 7, 9, the G3 banner, no Prospect
//   c  Segment Advisory: the Ridgeline project; the tiles recount to Accepted 1
//   d  "Harbor Lane" matches nothing: "No engagements match 'Harbor Lane'." and Clear filters
//   e  the list never answers: skeleton tile counts and 8 skeleton rows
//
// Every outbound target but ENG-02 (ENG-03, ENG-04, SIG-01, CLS-02, TAX-02, AUD-02, NOT-02,
// PRJ-01) is planned: sub-lines and the letter cell are plain text, "+ New engagement" is drawn
// disabled with its hint outside production. Export is cut (P-07 §2.3).

export interface ENG01Props {
  filters: EngagementFilters;
  onFilters: (next: EngagementFilters) => void;
  /** Open an engagement's record (ENG-02). */
  onOpen?: (engagementId: string) => void;
}

const FORMS = /\b(1040|1041|1065|1120-?S|1120|990|706|709)\b/g;

/** "CAS · Monthly close", "Tax · 1065", "Tax · 1040 · 1041 · 706" (the forms in the name). */
export function typeText(row: EngagementIndexRowOut): string {
  const line = COPY.lines[row.service_line];
  if (row.type === "tax_compliance") {
    const forms = [...new Set(row.name.match(FORMS) ?? [])];
    if (forms.length > 0) return `${line} · ${forms.join(" · ")}`;
  }
  return `${line} · ${COPY.types[row.type]}`;
}

function nounOf(row: EngagementIndexRowOut, n: number): string {
  const kind = row.work_items?.[0]?.kind;
  let pair: readonly [string, string];
  if (kind === "assurance") {
    pair =
      row.type === "review"
        ? COPY.workItems.review
        : row.type === "preparation" || row.type === "compilation"
          ? COPY.workItems.engagement
          : COPY.workItems.audit;
  } else pair = kind === undefined ? COPY.workItems.engagement : COPY.workItems[kind];
  return n === 1 ? pair[0] : pair[1];
}

const DAY_MS = 86_400_000;

/** Whole calendar days from today (in the firm's zone) to `on`. */
export function daysTo(on: string, now: Date, tz: string): number {
  const today = isoDate(now, tz);
  return Math.round((Date.parse(`${on}T12:00:00Z`) - Date.parse(`${today}T12:00:00Z`)) / DAY_MS);
}

/** Red ink at ≤ 7 days, amber at ≤ 30, ink-2 beyond (the acceptance checklist). */
function dueTone(days: number): string {
  if (days <= 7) return "text-red-ink";
  if (days <= 30) return "text-amber-ink";
  return "text-ink-2";
}

/** The registry's pill colours for the `engagement` object are all tile colours. */
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

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

function LetterCell({
  letter,
  now,
  tz,
}: {
  letter: EngagementLetterSummaryOut;
  now: Date;
  tz: string;
}): JSX.Element {
  const on = (d: string | null | undefined): string =>
    d == null ? DASH : date(onDay(d), { now, tz });
  const signed = letter.signed_count ?? 0;
  const signers = letter.signer_count ?? 0;
  if (letter.status === "signed") {
    return (
      <Pill variant="green-tint" size="micro">
        {COPY.letter.signed(on(letter.signed_on))}
      </Pill>
    );
  }
  if (letter.last_event === "sent" || letter.last_event === "viewed") {
    const text = (letter.last_event === "sent" ? COPY.letter.sent : COPY.letter.viewed)(
      on(letter.last_event_on),
      signed,
      signers,
    );
    return (
      <Pill variant="amber" size="micro">
        {text}
      </Pill>
    );
  }
  if (signers > 0) {
    return (
      <Pill variant="amber" size="micro">
        {COPY.letter.partial(signed, signers)}
      </Pill>
    );
  }
  return <span className="text-ink-4">{COPY.letter.none}</span>;
}

function WorkItemsCell({ row }: { row: EngagementIndexRowOut }): JSX.Element {
  const lines = row.work_items ?? [];
  const first = lines[0];
  if (first === undefined) {
    const waiting =
      row.status === "prospect"
        ? COPY.workItems.prospect
        : row.letter.status !== "signed"
          ? COPY.workItems.waitingLetter
          : null;
    return (
      <span className="flex min-w-0 flex-col">
        <span className="text-ink-4">{DASH}</span>
        {waiting !== null && <SubLine>{waiting}</SubLine>}
      </span>
    );
  }
  const pill =
    first.pill_object != null && first.pill_code != null
      ? status(first.pill_object as RegistryObject, first.pill_code as never)
      : null;
  return (
    <span className="flex min-w-0 flex-col">
      <span>{`${count(lines.length)} ${nounOf(row, lines.length)}`}</span>
      <span className="flex min-w-0 items-center gap-[4px]">
        <SubLine>{first.label}</SubLine>
        {pill !== null && (
          <Pill variant={pill.variant ?? "neutral"} size="micro">
            {pill.label}
          </Pill>
        )}
      </span>
    </span>
  );
}

function NextDueCell({
  row,
  now,
  tz,
}: {
  row: EngagementIndexRowOut;
  now: Date;
  tz: string;
}): JSX.Element {
  const due = row.next_due;
  if (due == null) return <span className="text-ink-4">{DASH}</span>;
  const days = daysTo(due.on, now, tz);
  const label = due.label ?? null;
  let sub: string;
  if (days < 0) {
    sub = label === null ? COPY.due.pastDue(-days) : `${label} · ${COPY.due.pastDue(-days)}`;
  } else sub = label ?? COPY.due.days(days);
  return (
    <span className="flex min-w-0 flex-col items-end">
      <span>{date(onDay(due.on), { now, tz })}</span>
      <span
        data-due={days < 0 ? "past" : days <= 7 ? "red" : days <= 30 ? "amber" : "ink"}
        className={cn("max-w-full truncate text-meta", dueTone(days), days < 0 && "font-medium")}
      >
        {sub}
      </span>
    </span>
  );
}

function EngagementPill({ code }: { code: EngagementStatus }): JSX.Element {
  const word = status("engagement", code);
  return (
    <StatusPill variant={word.variant ?? "neutral"} size="state">
      {code === "archived" && <Icon name="lock" size={12} />}
      {word.label}
    </StatusPill>
  );
}

/** The screen with its own filters: the route's page and the gallery's artboard. `initial` is what
 * an artboard opens on (b: Letter │ Not signed with Accepted; c: Advisory; d: "Harbor Lane"). */
export function EngagementsIndex({
  initial = {},
  onOpen,
}: {
  initial?: Partial<EngagementFilters>;
  onOpen?: (engagementId: string) => void;
}): JSX.Element {
  const [filters, setFilters] = useState<EngagementFilters>(() => ({
    ...DEFAULT_ENGAGEMENT_FILTERS,
    ...initial,
  }));
  return (
    <ENG01
      filters={filters}
      onFilters={setFilters}
      {...(onOpen === undefined ? {} : { onOpen })}
    />
  );
}

export function ENG01({ filters, onFilters, onOpen }: ENG01Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const list = useEngagementIndex(filters);
  const canCreate = useCan("engagement.create");
  const staff = useStaff();

  const pages: EngagementIndexPage[] = list.data?.pages ?? [];
  const first = pages[0];
  const last = pages[pages.length - 1];
  const items = pages.flatMap((p) => p.items);
  const narrowed = isNarrowedIndex(filters) || filters.line !== null;
  const set = (patch: Partial<EngagementFilters>): void => {
    onFilters({ ...filters, ...patch });
  };
  const clear = (): void => {
    onFilters({ ...DEFAULT_ENGAGEMENT_FILTERS, line: filters.line });
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

  const envelope: ListEnvelope<EngagementIndexRowOut> | undefined =
    first === undefined
      ? undefined
      : {
          items,
          next_cursor: last?.next_cursor ?? null,
          total: first.total,
          counts: first.counts ?? {},
          facets: first.facets ?? {},
        };

  // The segments are the server's facets; "All" is their sum, which the server foots to `total`.
  const facets = first?.facets?.service_line ?? [];
  const segmentCount = (line: EngagementLine): number =>
    facets.find((f) => f.value === line)?.n ?? 0;
  const allCount = facets.reduce((sum, f) => sum + f.n, 0);
  const segments = (
    <Segmented
      size="small"
      label={COPY.segmentsLabel}
      options={[
        { label: COPY.segments.all, ...(first === undefined ? {} : { count: allCount }) },
        ...ENGAGEMENT_LINES.map((line) => ({
          label: COPY.segments[line],
          ...(first === undefined ? {} : { count: segmentCount(line) }),
        })),
      ]}
      active={filters.line === null ? COPY.segments.all : COPY.segments[filters.line]}
      onChange={(label) => {
        const line = ENGAGEMENT_LINES.find((l) => COPY.segments[l] === label) ?? null;
        set({ line: isEngagementLine(line) ? line : null, tile: null });
      }}
    />
  );

  const chips: IndexChip[] = [
    {
      key: "office",
      label: COPY.chips.office,
      icon: "map-pin",
      options: officeOptions(items),
      value: filters.office,
      placeholder: COPY.chips.allOffices,
    },
    {
      key: "partner",
      label: COPY.chips.partner,
      icon: "circle-user-round",
      options: partnerOptions(items),
      value: filters.partner,
      placeholder: COPY.chips.all,
    },
    {
      key: "letter",
      label: COPY.chips.letter,
      icon: "signature",
      options: [
        { value: "not_signed", label: COPY.chips.notSigned },
        { value: "signed", label: COPY.chips.signed },
      ],
      value: filters.letter,
      placeholder: COPY.chips.any,
    },
    {
      key: "nextDue",
      label: COPY.chips.nextDue,
      icon: "calendar",
      options: [
        { value: "past_due", label: COPY.chips.pastDue },
        { value: "within_7_days", label: COPY.chips.within7 },
        { value: "within_30_days", label: COPY.chips.within30 },
      ],
      value: filters.nextDue,
      placeholder: COPY.chips.any,
    },
    {
      key: "period",
      label: COPY.chips.period,
      icon: "clock",
      align: "end",
      options: [
        { value: "prior", label: COPY.chips.prior },
        { value: "all", label: COPY.chips.allPeriods },
      ],
      value: filters.period === "current" ? null : filters.period,
      placeholder: COPY.chips.current,
    },
  ];

  const onChip = (key: string, value: string | null): void => {
    if (key === "office") set({ office: value });
    else if (key === "partner") set({ partner: value });
    else if (key === "letter") {
      set({ letter: value === "not_signed" || value === "signed" ? value : null });
    } else if (key === "nextDue") {
      set({
        nextDue:
          value === "past_due" || value === "within_7_days" || value === "within_30_days"
            ? value
            : null,
      });
    } else if (key === "period") {
      set({ period: value === "prior" || value === "all" ? value : "current" });
    }
  };

  const tiles: IndexTile[] = ENGAGEMENT_TILES.map((code) => {
    const word = status("engagement", code);
    return { code, label: word.label, variant: tileVariant(word.variant) };
  });

  const summary =
    first === undefined
      ? undefined
      : COPY.summary(
          count(first.total),
          count(first.summary.prospect),
          count(first.summary.awaiting_letter),
          count(first.summary.past_due),
        );

  const columns: IndexColumn<EngagementIndexRowOut>[] = [
    {
      key: "engagement",
      header: COPY.columns.engagement,
      width: 200,
      cell: (r) => (
        <span
          title={COPY.rowHint(r.name)}
          className="block whitespace-normal leading-[1.25] line-clamp-2 font-medium"
        >
          {r.name}
        </span>
      ),
    },
    {
      key: "client",
      header: COPY.columns.client,
      cell: (r) => <span className="block truncate">{r.client_name}</span>,
    },
    {
      key: "type",
      header: COPY.columns.type,
      width: 128,
      cell: (r) => (
        <span className="block whitespace-normal leading-[1.25] line-clamp-2 text-ink-2">
          {typeText(r)}
        </span>
      ),
    },
    {
      key: "period",
      header: COPY.columns.period,
      width: 104,
      cell: (r) => (
        <span className="block whitespace-normal leading-[1.25] line-clamp-2 text-ink-2">
          {r.period_label ?? DASH}
        </span>
      ),
    },
    {
      key: "office",
      header: COPY.columns.office,
      width: 84,
      cell: (r) => <span className="text-ink-2">{r.office_name ?? DASH}</span>,
    },
    {
      key: "partner",
      header: COPY.columns.partner,
      width: 60,
      cell: (r) =>
        r.partner_initials == null ? (
          DASH
        ) : (
          <abbr
            title={
              (r.partner_user_id == null ? undefined : staff.names.get(r.partner_user_id)) ??
              r.partner_initials
            }
            className="text-dense text-ink-2 no-underline"
          >
            {r.partner_initials}
          </abbr>
        ),
    },
    {
      key: "status",
      header: COPY.columns.status,
      width: 108,
      cell: (r) => <EngagementPill code={r.status} />,
    },
    {
      key: "work",
      header: COPY.columns.workItems,
      width: 150,
      cell: (r) => <WorkItemsCell row={r} />,
    },
    {
      key: "letter",
      header: COPY.columns.letter,
      width: 150,
      cell: (r) => <LetterCell letter={r.letter} now={now} tz={tz} />,
    },
    {
      key: "due",
      header: COPY.columns.nextDue,
      width: 170,
      align: "right",
      cell: (r) => <NextDueCell row={r} now={now} tz={tz} />,
    },
  ];

  // ENG-03 is planned: "+ New engagement" is drawn for `engagement.create` holders, disabled with
  // its hint, and not at all in production (docs/screens/ENG-01.md, Links).
  const newButton =
    canCreate && PLANNED_VISIBLE ? (
      <Button variant="primary" icon="plus" disabled title={COPY.newEngagementHint}>
        {COPY.newEngagement}
      </Button>
    ) : undefined;

  const showBanner = filters.letter === "not_signed" && state.kind === "ready";
  const countText =
    first === undefined ? undefined : COPY.showing(count(items.length), count(first.total));

  return (
    <div data-screen="ENG-01" className="flex min-h-0 flex-1 flex-col">
      <IndexList<EngagementIndexRowOut>
        title={COPY.title}
        noun={COPY.noun}
        state={state}
        envelope={envelope}
        columns={columns}
        rowKey={(r) => r.id}
        {...(onOpen === undefined
          ? {}
          : {
              onOpen: (r: EngagementIndexRowOut) => {
                onOpen(r.id);
              },
              onSelect: (r: EngagementIndexRowOut) => {
                onOpen(r.id);
              },
            })}
        twoLine={() => true}
        segments={segments}
        chips={chips}
        onChip={onChip}
        tiles={tiles}
        tile={filters.tile}
        onTile={(code) => {
          set({ tile: isEngagementTile(code) ? code : null });
        }}
        {...(summary === undefined ? {} : { summary })}
        {...(isNarrowedIndex(filters) ? { onClear: clear } : {})}
        query={filters.q}
        searchPlaceholder={COPY.search}
        onQuery={(q) => {
          set({ q });
        }}
        {...(countText === undefined ? {} : { countText })}
        {...(newButton === undefined ? {} : { actions: newButton })}
        {...(showBanner ? { banner: COPY.bannerG3 } : {})}
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
        empty={{ icon: "briefcase", title: COPY.empty.title }}
      />
    </div>
  );
}

function officeOptions(rows: readonly EngagementIndexRowOut[]) {
  const seen = new Map<string, string>();
  for (const r of rows) {
    if (r.office_id != null && r.office_name != null) seen.set(r.office_id, r.office_name);
  }
  return [...seen].map(([value, label]) => ({ value, label }));
}

function partnerOptions(rows: readonly EngagementIndexRowOut[]) {
  const seen = new Map<string, string>();
  for (const r of rows) {
    if (r.partner_user_id != null && r.partner_initials != null) {
      seen.set(r.partner_user_id, r.partner_initials);
    }
  }
  return [...seen].map(([value, label]) => ({ value, label }));
}
