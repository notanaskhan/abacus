import type { TaxReturnRowOut, TaxReturnSummaryOut } from "@abacus/api-client";
import {
  bulkAssignMutation,
  firmMembersOptions,
  listReturnsOptions,
  officesOptions,
  returnsSummaryOptions,
} from "@abacus/api-client/query";
import {
  Button,
  Checkbox,
  type IndexColumn,
  IndexList,
  type IndexTile,
  type ListEnvelope,
  Menu,
  Popover,
  RegistryStatus,
  SignerChips,
  SyncChip,
  Tooltip,
  type ViewState,
  date as formatDate,
  status,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { COPY } from "./copy";

// TAX-01 · Tax Returns practice board (T-02-T12; docs/screens/TAX-01.md) on TPL-01's T1 grammar,
// over `GET /v1/tax-returns` and `/summary` (T-02-T09). Every artboard is a data condition:
//
//   a  default: 15 of 79 open by due date     b  ?tile=awaiting_signature (signer chips)
//   c  ?office=grouped (office bands)          d  bulk selection (Feld, Shah, Varga)
//   e  ?q=Schwab (filtered empty)              f  ?tax_year=2026 (season start)
//   g  loading (the rows never answer; the tiles hold their place with skeleton counts, T1e)
//
// Assign preparer is live (`POST :bulk-assign`); Extend… and Run firm standards… are planned and
// shown only in fixture builds (PLANNED_VISIBLE). There is no Board toggle in the pilot (DV-15).

export interface Tax01Search {
  tile?: string;
  office?: string;
  q?: string;
  tax_year?: string;
}
const KEYS = ["tile", "office", "q", "tax_year"] as const;
const PAGE = 15;
const TAX_YEAR = 2025;
const OPEN = [
  "not_started",
  "gathering",
  "preparing",
  "prepared",
  "in_review",
  "action_required",
  "approved",
  "awaiting_signature",
] as const;
const TILE_ORDER = [
  "prepared",
  "in_review",
  "action_required",
  "approved",
  "gathering",
  "preparing",
  "awaiting_signature",
  "filed_accepted",
] as const;
const TILE_VARIANTS: Readonly<
  Record<(typeof TILE_ORDER)[number], NonNullable<IndexTile["variant"]>>
> = {
  prepared: "neutral",
  in_review: "state",
  action_required: "red-tint",
  approved: "green-tint",
  gathering: "neutral",
  preparing: "neutral",
  awaiting_signature: "amber",
  filed_accepted: "green-tint",
};

function tileLabel(code: (typeof TILE_ORDER)[number]): string {
  if (code === "filed_accepted") {
    return `${status("return", "filed").label} · ${status("return", "accepted").label}`;
  }
  return status("return", code, { context: "home_and_tax_tiles" }).label;
}

const TILES: readonly IndexTile[] = TILE_ORDER.map((code) => ({
  code,
  label: tileLabel(code),
  variant: TILE_VARIANTS[code],
}));

function due(r: TaxReturnRowOut): string | null {
  return r.extended_due_on ?? r.original_due_on;
}

function daysTo(iso: string, now: Date): number {
  const today = now.toISOString().slice(0, 10);
  return Math.round(
    (Date.parse(`${iso}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86_400_000,
  );
}

/** ≤ 7 days red-ink, ≤ 30 amber-ink, later ink-2 (TPL-01 acceptance). */
function daysTone(days: number): string {
  if (days <= 7) return "text-red-ink";
  if (days <= 30) return "text-amber-ink";
  return "text-ink-2";
}

function counts(summary: TaxReturnSummaryOut | undefined): Record<string, number> {
  const out: Record<string, number> = Object.fromEntries(TILE_ORDER.map((t) => [t, 0]));
  for (const t of summary?.tiles ?? []) {
    const code = t.status === "filed" || t.status === "accepted" ? "filed_accepted" : t.status;
    out[code] = (out[code] ?? 0) + t.count;
  }
  return out;
}

export interface TAX01Props {
  search: Tax01Search;
  onSearch: (next: Tax01Search) => void;
  onOpen?: (row: TaxReturnRowOut) => void;
  /** The returns selected on open (artboard d's selection; the gallery and tests). */
  initialSelection?: readonly string[];
}

export function TAX01({
  search,
  onSearch,
  onOpen,
  initialSelection = [],
}: TAX01Props): JSX.Element {
  const now = useNow();
  const year = Number(search.tax_year ?? TAX_YEAR);
  const grouped = search.office === "grouped";
  const tile = search.tile ?? null;
  const statuses =
    tile === null ? [...OPEN] : tile === "filed_accepted" ? ["filed", "accepted"] : [tile];
  // Query keys hash by value: a fresh object each render is the same query.
  const query = {
    tax_year: year,
    status: statuses as TaxReturnRowOut["status"][],
    ...(search.q === undefined ? {} : { q: search.q }),
    ...(grouped ? { group_by: "office" as const } : {}),
  };
  const list = useQuery(listReturnsOptions({ query }));
  const summary = useQuery(returnsSummaryOptions({ query: { tax_year: year } }));
  const offices = useQuery(officesOptions());
  const members = useQuery(firmMembersOptions());
  const [picking, setPicking] = useState(false);
  const assign = useMutation(bulkAssignMutation());
  const [chosen, setChosen] = useState<ReadonlySet<string>>(() => new Set(initialSelection));
  const set = (patch: Partial<Record<keyof Tax01Search, string | undefined>>): void => {
    const next = { ...search, ...patch };
    const clean: Tax01Search = {};
    for (const key of KEYS) {
      const value = next[key];
      if (value !== undefined && value !== "") clean[key] = value;
    }
    setChosen(new Set());
    onSearch(clean);
  };

  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const envelope: ListEnvelope<TaxReturnRowOut> | undefined =
    list.data === undefined
      ? undefined
      : {
          items: grouped ? items : items.slice(0, PAGE),
          next_cursor: null,
          total,
          counts: counts(summary.data),
        };
  const officeName = (id: string | null): string =>
    offices.data?.find((o) => o.id === id)?.name ?? "";
  const officeTotals = (id: string | null): { open: number; done: number } =>
    summary.data?.offices.find((o) => o.office_id === id) ?? { open: 0, done: 0 };
  const allTotal = summary.data?.total ?? 0;
  const viewState: ViewState = list.isPending
    ? { kind: "loading" }
    : list.isError
      ? {
          kind: "error",
          retry: () => {
            void list.refetch();
          },
        }
      : allTotal === 0
        ? {
            kind: "empty",
            action: { label: COPY.openSeasonSetup, onSelect: () => undefined },
          }
        : search.q !== undefined && total === 0
          ? {
              kind: "filtered-empty",
              query: search.q,
              title: COPY.noResults(search.q),
              clear: () => {
                set({ q: undefined, tile: undefined, office: undefined });
              },
            }
          : { kind: "ready" };

  const toggle = (id: string, on: boolean): void => {
    setChosen((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const columns: IndexColumn<TaxReturnRowOut>[] = [
    {
      key: "select",
      header: "",
      width: 32,
      cell: (r) => (
        <span
          onClick={(e) => {
            e.stopPropagation();
          }}
        >
          <Checkbox
            label={COPY.select(r.client_name)}
            checked={chosen.has(r.id)}
            onChange={(on) => {
              toggle(r.id, on);
            }}
          />
        </span>
      ),
    },
    {
      key: "return",
      header: COPY.columns.return,
      width: 92,
      cell: (r) => (
        <span className="text-cell font-medium text-ink">
          {r.form === "1120s" ? "1120-S" : r.form}
        </span>
      ),
    },
    {
      key: "client",
      header: COPY.columns.client,
      cell: (r) => (
        <span className="inline-flex min-w-0 items-center gap-[6px]">
          <span className="truncate">{r.client_name}</span>
          {r.tags.includes("draft_k1") && (
            <Popover
              label={COPY.draftK1}
              width={300}
              align="start"
              trigger={
                <button type="button" className="text-meta text-amber-ink hover:underline">
                  {COPY.draftK1}
                </button>
              }
            >
              <div className="flex flex-col gap-[6px] p-[12px] text-body text-ink-2">
                <p>{COPY.draftK1Detail}</p>
                <Tooltip content={COPY.openTxp12Tip}>
                  <span className="font-medium text-ink">{COPY.openTxp12}</span>
                </Tooltip>
              </div>
            </Popover>
          )}
        </span>
      ),
    },
    {
      key: "office",
      header: COPY.columns.office,
      width: 96,
      cell: (r) => officeName(r.office_id),
    },
    {
      key: "prep",
      header: COPY.columns.prepRev,
      width: 86,
      cell: (r) => `${r.preparer?.initials ?? "—"} / ${r.reviewer?.initials ?? "—"}`,
    },
    {
      key: "status",
      header: COPY.columns.status,
      width: 168,
      cell: (r) => (
        <RegistryStatus
          object="return"
          code={r.status}
          {...(r.review_level === null
            ? {}
            : {
                vars: { level: r.review_level.charAt(0).toUpperCase() + r.review_level.slice(1) },
              })}
        />
      ),
    },
    {
      key: "issues",
      header: COPY.columns.issues,
      align: "right",
      width: 64,
      cell: (r) =>
        r.issues === null || r.issues === undefined || r.issues === 0 ? (
          <span className="text-ink-4">—</span>
        ) : (
          <span className="rounded-pill bg-red-tint px-[6px] text-red-ink">
            {String(r.issues)}
          </span>
        ),
    },
    {
      key: "sync",
      header: COPY.columns.sync,
      width: 150,
      cell: (r) =>
        r.sync === null ? null : (
          <Tooltip content={COPY.syncTip}>
            <span>
              <SyncChip code={r.sync} />
            </span>
          </Tooltip>
        ),
    },
    {
      key: "due",
      header: COPY.columns.due,
      width: 110,
      cell: (r) => {
        const on = due(r);
        if (on === null) return "—";
        return (
          <span className="inline-flex items-center gap-[6px]">
            <Popover
              label={COPY.dueRule(r.client_name)}
              width={300}
              align="start"
              trigger={
                <button
                  type="button"
                  className="text-cell text-ink underline-offset-2 hover:underline"
                >
                  {formatDate(on, { now })}
                </button>
              }
            >
              <p className="p-[12px] text-body text-ink-2">{r.due_rule_code ?? ""}</p>
            </Popover>
            {r.extended && (
              <span className="rounded-tile bg-nested px-[5px] text-meta text-ink-2">
                {COPY.extended}
              </span>
            )}
          </span>
        );
      },
    },
    {
      key: "days",
      header: COPY.columns.days,
      align: "right",
      width: 72,
      cell: (r) => {
        const on = due(r);
        if (on === null) return "—";
        const n = daysTo(on, now);
        return <span className={daysTone(n)}>{COPY.days(n)}</span>;
      },
    },
    ...(tile === "awaiting_signature"
      ? [
          {
            key: "signature",
            header: COPY.columns.signature,
            width: 150,
            cell: (r: TaxReturnRowOut) => (
              <Tooltip content={COPY.signerTip}>
                <span>
                  <SignerChips
                    chips={(r.signers ?? []).map((s, i) => ({
                      signerId: `${r.id}-${String(i)}`,
                      name: s.name,
                      status: s.signed ? ("signed" as const) : ("pending" as const),
                    }))}
                  />
                </span>
              </Tooltip>
            ),
          },
        ]
      : []),
  ];

  const open = summary.data?.open ?? 0;
  const done = summary.data?.done ?? 0;
  const extended = summary.data?.extended ?? 0;
  const assignTo = (userId: string): void => {
    assign.mutate(
      {
        body: { return_ids: [...chosen], role: "preparer", user_id: userId },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      {
        onSuccess: (out) => {
          toast.show(COPY.assigned(out.assigned));
          setChosen(new Set());
        },
      },
    );
  };
  // Extend… and Run firm standards… are planned: drawn disabled in fixture builds, absent in
  // production (chapter 04 §2.1 rule 4).
  const planned = PLANNED_VISIBLE
    ? [
        { label: COPY.bulk.extend, onSelect: () => undefined, disabled: true },
        { label: COPY.bulk.standards, onSelect: () => undefined, disabled: true },
      ]
    : [];
  const bulk = (
    <Menu
      label={COPY.bulkActions}
      trigger={
        <Button variant="secondary" size="sm">
          {COPY.bulkActions}
        </Button>
      }
      sections={[
        [
          {
            label: COPY.bulk.assign,
            onSelect: () => {
              setPicking(true);
            },
            disabled: chosen.size === 0,
            opensDialog: true,
          },
          ...planned,
        ],
      ]}
    />
  );

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <IndexList<TaxReturnRowOut>
        title={COPY.title}
        noun="returns"
        state={viewState}
        envelope={envelope}
        columns={columns}
        rowKey={(r) => r.id}
        {...(onOpen === undefined ? {} : { onOpen })}
        {...(grouped
          ? {
              groupOf: (r: TaxReturnRowOut) => {
                const t = officeTotals(r.office_id);
                return {
                  key: r.office_id ?? "",
                  label: COPY.officeBand(officeName(r.office_id), t.open + t.done, t.open, t.done),
                };
              },
            }
          : {})}
        chips={[
          {
            key: "form",
            label: COPY.filters.form,
            options: [],
            value: null,
            placeholder: COPY.filterAll,
          },
          {
            key: "office",
            label: COPY.filters.office,
            options: [{ value: "grouped", label: COPY.grouped }],
            value: grouped ? "grouped" : null,
            placeholder: COPY.allOffices,
          },
          {
            key: "partner",
            label: COPY.filters.partner,
            options: [],
            value: null,
            placeholder: COPY.filterAll,
          },
          {
            key: "preparer",
            label: COPY.filters.preparer,
            options: [],
            value: null,
            placeholder: COPY.filterAll,
          },
          {
            key: "due",
            label: COPY.filters.due,
            options: [],
            value: null,
            placeholder: COPY.next60,
          },
          {
            key: "tax_year",
            label: COPY.filters.taxYear,
            options: [
              { value: String(TAX_YEAR), label: `TY${String(TAX_YEAR)}` },
              { value: String(TAX_YEAR + 1), label: `TY${String(TAX_YEAR + 1)}` },
            ],
            value: String(year),
            align: "end",
          },
        ]}
        onChip={(key, value) => {
          if (key === "tax_year") set({ tax_year: value ?? undefined, tile: undefined });
          if (key === "office") set({ office: value ?? undefined });
        }}
        tiles={TILES}
        tile={tile}
        onTile={(code) => {
          set({ tile: code ?? undefined });
        }}
        summary={COPY.summary(open, done, allTotal, year, extended)}
        onClear={() => {
          set({ tile: undefined, office: undefined, q: undefined });
        }}
        query={search.q ?? ""}
        onQuery={(q) => {
          set({ q: q === "" ? undefined : q });
        }}
        searchPlaceholder={COPY.search}
        newLabel={COPY.newReturn}
        onNew={() => undefined}
        countText={COPY.showing(envelope?.items.length ?? 0, total)}
        actions={bulk}
        empty={{ title: COPY.seasonEmptyTitle(year), body: COPY.seasonEmptyBody(year - 1) }}
      />
      {chosen.size > 0 && (
        <div
          role="region"
          aria-label={COPY.selected(chosen.size)}
          className="absolute top-[54px] right-[12px] left-[12px] flex h-[46px] items-center gap-[8px] rounded-pane bg-card px-[12px] shadow-e2"
        >
          <span className="text-body font-medium">{COPY.selected(chosen.size)}</span>
          <Menu
            label={COPY.assignTo}
            open={picking}
            onOpenChange={setPicking}
            disabled={assign.isPending}
            trigger={
              <Button size="sm" variant="secondary" loading={assign.isPending}>
                {COPY.bulk.assign}
              </Button>
            }
            sections={[
              (members.data ?? []).map((m) => ({
                label: m.display_name,
                onSelect: () => {
                  assignTo(m.user_id);
                },
              })),
            ]}
          />
          {planned.map((item) => (
            <Button key={item.label} size="sm" variant="secondary" disabled>
              {item.label}
            </Button>
          ))}
          <button
            type="button"
            className="ml-auto text-dense text-ink-2 hover:underline"
            onClick={() => {
              setChosen(new Set());
            }}
          >
            {COPY.clear}
          </button>
        </div>
      )}
    </div>
  );
}

/** The page with its search kept in state: the gallery's and the tests' host. */
export function TaxReturnsPage({
  initial = {},
  initialSelection = [],
  onOpen,
}: {
  initial?: Tax01Search;
  initialSelection?: readonly string[];
  onOpen?: (row: TaxReturnRowOut) => void;
}): JSX.Element {
  const [search, setSearch] = useState<Tax01Search>(initial);
  return (
    <TAX01
      search={search}
      onSearch={setSearch}
      initialSelection={initialSelection}
      {...(onOpen === undefined ? {} : { onOpen })}
    />
  );
}
