import {
  AppShell,
  Button,
  IndexList,
  type IndexColumn,
  type IndexTile,
  type ListEnvelope,
  type ViewState,
  date as formatDate,
  Menu,
  Popover,
  RegistryStatus,
  SignerChips,
  SyncChip,
  status,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  ENVELOPES,
  OPEN_STATUSES,
  type SeedTaxReturn,
  TAX_RETURNS,
  TAX_YEAR,
  TILE_ORDER,
  boardOrder,
} from "../../../fixtures/seed/tax";
import { useSession } from "../../../app-core/session";
import { AREAS } from "../../../app-core/nav-areas";
import type { FixtureParams } from "../../fixture-mode";
import { COPY } from "./copy";

// TPL-01 Tax Returns practice board specimen (F-06-T08; docs/screens/TPL-01.md; F-06 F2): Hannah
// Leclerc on the TY2025 board at E0, Mon Sep 14, 2026, 9:24 AM CT, over the tax seed (F-06-T02),
// on the T1 IndexList. a default (15 of 79 open by extended due date), b the Awaiting signature
// tile (exactly the ten returns behind E1 to E10, with their signer chips), c filtered empty
// ("Schwab"), d loading, e season start (TY2026: no returns, tiles 0). The specimen stands in for
// the server: the tiles read a `counts` facet computed here over the filters minus the tile, the
// list never adds rows up in the template. Registered for /components/screens/TPL-01?st=a…e.

export const TPL01_STATES = ["a", "b", "c", "d", "e"] as const;
export type Tpl01State = (typeof TPL01_STATES)[number];

/** The demo clock's day (E0). */
const TODAY = "2026-09-14";
const PAGE = 15;
const OPEN = new Set<string>(OPEN_STATUSES);

const TILE_VARIANTS: Readonly<
  Record<(typeof TILE_ORDER)[number], NonNullable<IndexTile["variant"]>>
> = {
  prepared: "neutral",
  in_review: "state",
  action_required: "red-tint",
  approved: "green-tint",
  gathering: "state",
  preparing: "state",
  awaiting_signature: "amber",
  filed_accepted: "green",
};

/** Tile words come from the registry (`home_and_tax_tiles`); "Filed · Accepted" joins two codes. */
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
  ...(code === "awaiting_signature" ? { mark: "dot" as const } : {}),
}));

/** Days from the demo clock to the due date (whole days; dates only, no time zone arithmetic). */
export function daysToDue(due: string, today: string = TODAY): number {
  const ms = Date.parse(`${due}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`);
  return Math.round(ms / 86_400_000);
}

/** ≤ 7 days red-ink, ≤ 30 amber-ink, later ink-2 (TPL-01 acceptance). */
export function daysTone(days: number): "text-red-ink" | "text-amber-ink" | "text-ink-2" {
  if (days <= 7) return "text-red-ink";
  if (days <= 30) return "text-amber-ink";
  return "text-ink-2";
}

function shortDate(iso: string): string {
  return formatDate(iso, { now: Date.parse(`${TODAY}T14:24:00Z`), withYear: true });
}

function DueCell({ row }: { row: SeedTaxReturn }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-[6px]">
      <Popover
        label={`Due date rule for ${row.client}`}
        width={300}
        align="start"
        trigger={
          <button type="button" className="text-cell text-ink underline-offset-2 hover:underline">
            {shortDate(row.due)}
          </button>
        }
      >
        <p className="p-[12px] text-body text-ink-2">{row.dueRule}</p>
      </Popover>
      {row.extended && <span className="text-meta text-ink-3">{COPY.extended}</span>}
    </span>
  );
}

function signatureCell(row: SeedTaxReturn): JSX.Element | null {
  const envelope = ENVELOPES.find((e) => e.key === row.envelope);
  if (envelope === undefined) return null;
  return (
    <SignerChips
      chips={envelope.signers.map((s, i) => ({
        signerId: `${envelope.key}-${String(i)}`,
        name: s.name,
        status: s.signed ? "signed" : "pending",
      }))}
    />
  );
}

const BASE_COLUMNS: readonly IndexColumn<SeedTaxReturn>[] = [
  {
    key: "return",
    header: COPY.columns.return,
    width: 168,
    cell: (r) => <span className="text-cell text-ink">{COPY.returnLabel(TAX_YEAR, r.form)}</span>,
  },
  { key: "client", header: COPY.columns.client, cell: (r) => r.client },
  {
    key: "office",
    header: COPY.columns.office,
    width: 97,
    cell: (r) => <span className="text-ink-3">{r.office}</span>,
  },
  {
    key: "prep",
    header: COPY.columns.prepRev,
    width: 86,
    cell: (r) => <span className="text-ink-3">{`${r.preparer} / ${r.reviewer}`}</span>,
  },
  {
    key: "status",
    header: COPY.columns.status,
    width: 172,
    cell: (r) => (
      <RegistryStatus
        object="return"
        code={r.status}
        context="tax_board_rows"
        {...(r.level === null ? {} : { vars: { level: r.level } })}
      />
    ),
  },
  {
    key: "issues",
    header: COPY.columns.issues,
    width: 66,
    align: "right",
    // An open count is a red-tinted badge; none reads "—" (the handoff's issue column).
    cell: (r) =>
      r.issues === null ? (
        <span className="text-ink-3">—</span>
      ) : (
        <span className="inline-flex h-[20px] min-w-[20px] items-center justify-center rounded-pill bg-red-tint px-[6px] text-meta text-red-ink">
          {String(r.issues)}
        </span>
      ),
  },
  {
    key: "sync",
    header: COPY.columns.sync,
    width: 164,
    cell: (r) => (
      <SyncChip
        code={r.sync.code}
        {...(r.sync.code === "synced" ? { vars: { date: r.sync.date } } : {})}
      />
    ),
  },
  {
    key: "due",
    header: COPY.columns.due,
    width: 110,
    align: "right",
    cell: (r) => <DueCell row={r} />,
  },
  {
    key: "days",
    header: COPY.columns.days,
    width: 76,
    align: "right",
    cell: (r) => {
      const n = daysToDue(r.due);
      return <span className={daysTone(n)}>{COPY.days(n)}</span>;
    },
  },
];

/** TPL-01b adds the signer chips; the default board (a) draws no Signature column. */
const SIGNATURE_COLUMN: IndexColumn<SeedTaxReturn> = {
  key: "signature",
  header: COPY.columns.signature,
  width: 150,
  cell: (r) => signatureCell(r),
};

interface Board {
  tile: string | null;
  query: string;
  year: number;
}

function tileOf(row: SeedTaxReturn): string {
  return row.status === "filed" || row.status === "accepted" ? "filed_accepted" : row.status;
}

/** The fixture server: the board's envelope for the filters. `counts` is over the filters minus
 * the tile (so a tile never counts itself out); `total` is the open rows that match. */
export function boardEnvelope(board: Board): ListEnvelope<SeedTaxReturn> {
  const year = board.year === TAX_YEAR ? TAX_RETURNS : [];
  const q = board.query.trim().toLowerCase();
  const matching = year.filter((r) => q === "" || r.client.toLowerCase().includes(q));
  const counts: Record<string, number> = Object.fromEntries(TILE_ORDER.map((t) => [t, 0]));
  for (const r of matching) {
    const t = tileOf(r);
    counts[t] = (counts[t] ?? 0) + 1;
  }
  const rows = boardOrder(
    board.tile === null
      ? matching.filter((r) => OPEN.has(r.status))
      : matching.filter((r) => tileOf(r) === board.tile),
  );
  return { items: rows.slice(0, PAGE), next_cursor: null, total: rows.length, counts };
}

const INITIAL: Readonly<Record<Tpl01State, Board>> = {
  a: { tile: null, query: "", year: TAX_YEAR },
  b: { tile: "awaiting_signature", query: "", year: TAX_YEAR },
  c: { tile: null, query: "Schwab", year: TAX_YEAR },
  d: { tile: null, query: "", year: TAX_YEAR },
  e: { tile: null, query: "", year: TAX_YEAR + 1 },
};

export function Tpl01Specimen({ state }: { state: Tpl01State }): JSX.Element {
  const [board, setBoard] = useState<Board>(INITIAL[state]);
  const envelope = boardEnvelope(board);
  const all = board.year === TAX_YEAR ? TAX_RETURNS : [];
  const open = all.filter((r) => OPEN.has(r.status)).length;
  const extended = all.filter((r) => r.extended).length;
  const filtered = board.query.trim() !== "" && envelope.total === 0;
  const viewState: ViewState =
    state === "d"
      ? { kind: "loading" }
      : all.length === 0
        ? { kind: "empty", action: { label: COPY.openSeasonSetup, onSelect: () => undefined } }
        : filtered
          ? {
              kind: "filtered-empty",
              query: board.query,
              title: COPY.noResults(board.query),
              clear: () => {
                setBoard(INITIAL.a);
              },
            }
          : { kind: "ready" };
  return (
    <div data-specimen="tpl-01" className="flex h-full min-h-0 flex-col overflow-hidden">
      <IndexList<SeedTaxReturn>
        title={COPY.title}
        noun="returns"
        state={viewState}
        envelope={envelope}
        columns={
          board.tile === "awaiting_signature" ? [...BASE_COLUMNS, SIGNATURE_COLUMN] : BASE_COLUMNS
        }
        rowKey={(r) => r.id}
        chips={[
          {
            key: "form",
            icon: "file-text",
            label: COPY.filters.form,
            options: [],
            value: null,
            placeholder: COPY.filterAll,
          },
          {
            key: "office",
            icon: "map-pin",
            label: COPY.filters.office,
            options: [],
            value: null,
            placeholder: COPY.allOffices,
          },
          {
            key: "partner",
            icon: "user-round",
            label: COPY.filters.partner,
            options: [],
            value: null,
            placeholder: COPY.filterAll,
          },
          {
            key: "preparer",
            icon: "user-round",
            label: COPY.filters.preparer,
            options: [],
            value: null,
            placeholder: COPY.filterAll,
          },
          {
            key: "due",
            icon: "calendar",
            label: COPY.filters.due,
            options: [],
            value: null,
            placeholder: COPY.next60,
          },
          {
            key: "tax_year",
            label: COPY.filters.taxYear,
            options: [
              { value: String(TAX_YEAR), label: String(TAX_YEAR) },
              { value: String(TAX_YEAR + 1), label: String(TAX_YEAR + 1) },
            ],
            // The current year is the board's default, not a filter: no Clear (TPL-01a).
            value: board.year === TAX_YEAR ? null : String(board.year),
            placeholder: String(TAX_YEAR),
            align: "end",
          },
        ]}
        onChip={(key, value) => {
          if (key === "tax_year") {
            setBoard({ ...board, year: value === null ? TAX_YEAR : Number(value), tile: null });
          }
        }}
        tiles={TILES}
        tile={board.tile}
        onTile={(code) => {
          setBoard({ ...board, tile: code });
        }}
        summary={COPY.summary(open, all.length - open, all.length, board.year, extended)}
        onClear={() => {
          setBoard(INITIAL.a);
        }}
        query={board.query}
        onQuery={(query) => {
          setBoard({ ...board, query });
        }}
        searchPlaceholder={COPY.search}
        newLabel={COPY.newReturn}
        onNew={() => undefined}
        countText={COPY.showing(envelope.items.length, envelope.total)}
        actions={
          <Menu
            label={COPY.bulkActions}
            trigger={
              <Button variant="secondary" size="sm">
                {COPY.bulkActions}
              </Button>
            }
            sections={[
              [
                { label: COPY.bulk.assign, onSelect: () => undefined, opensDialog: true },
                { label: COPY.bulk.extend, onSelect: () => undefined, opensDialog: true },
                { label: COPY.bulk.standards, onSelect: () => undefined, opensDialog: true },
              ],
            ]}
          />
        }
        empty={{
          title: COPY.seasonEmptyTitle(board.year),
          body: COPY.seasonEmptyBody(board.year - 1),
        }}
      />
    </div>
  );
}

export function Tpl01Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: Tpl01State = TPL01_STATES.find((s) => s === params.st) ?? "a";
  return <Tpl01Frame state={state} />;
}

/** The handoff draws the board inside the firm app: the T1 toolbar with Tax Returns current. */
function Tpl01Frame({ state }: { state: Tpl01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const toolbar = {
    nav: AREAS.map((a) => ({ label: a.label })),
    active: "Tax Returns",
    overflow: "none" as const,
    firm,
  };
  return (
    <div data-artboard={`tpl-01${state}`}>
      <AppShell frame height={860} toolbar={toolbar}>
        <Tpl01Specimen key={state} state={state} />
      </AppShell>
    </div>
  );
}
