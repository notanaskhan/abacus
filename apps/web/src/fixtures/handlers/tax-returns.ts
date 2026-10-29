// Fixture handlers for the tax-returns v1 reads (T-02-T08; rows since T-02-T12): TAX-01's summary
// and rows as the live routes answer them (T-02-T09), over the TY2025 board seed (F-06-T02, the
// Python slice's mirror, T-02-T11). Filters, the sort allowlist and office grouping run here as
// the server runs them; the screen never filters or adds rows up.
import type {
  TaxReturnOverviewOut,
  TaxReturnRecordOut,
  TaxReturnRowOut,
  TaxReturnSummaryOut,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { SEATS } from "../seed/people";
import { stableId } from "../seed/prng";
import { ENVELOPES, type SeedTaxReturn, TAX_RETURNS, TAX_YEAR } from "../seed/tax";
import { OVERVIEWS, type OverviewVariant } from "../seed/tax-return-overview";
import { TY2025_SUMMARY } from "../seed/tax-returns";

const FORM: Readonly<Record<SeedTaxReturn["form"], TaxReturnRowOut["form"]>> = {
  "1040": "1040",
  "1041": "1041",
  "1065": "1065",
  "1120-S": "1120s",
  "1120": "1120",
  "990": "990",
  "990-PF": "990",
};

/** TAX-01's spec: the Feld and Meera Shah rows wait on Ridgeline's draft K-1 (not yet released). */
const DRAFT_K1: ReadonlySet<string> = new Set(["Jonah & Claire Feld", "Meera Shah"]);

function slug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export function officeId(name: string): string {
  return stableId(`office:${name}`);
}

/** A seat's person chip by initials (TAX-01 rows; TAX-02's Team ladder). */
export function chip(initials: string): TaxReturnRowOut["preparer"] {
  const seat = SEATS.find((s) => s.initials === initials);
  return seat === undefined
    ? null
    : { user_id: stableId(`user:${slug(seat.name)}`), initials, name: seat.name };
}

export function rowOf(r: SeedTaxReturn): TaxReturnRowOut {
  const envelope = ENVELOPES.find((e) => e.key === r.envelope);
  return {
    id: r.id,
    client_id: stableId(`client:${slug(r.client)}`),
    client_name: r.client,
    form: FORM[r.form],
    tax_year: TAX_YEAR,
    status: r.status,
    review_level:
      r.level === null
        ? null
        : (r.level.toLowerCase() as NonNullable<TaxReturnRowOut["review_level"]>),
    extended: r.extended,
    on_hold: false,
    sync: r.sync.code,
    preparer: chip(r.preparer),
    reviewer: chip(r.reviewer),
    signer: null,
    office_id: officeId(r.office),
    original_due_on: r.extended ? null : r.due,
    extended_due_on: r.extended ? r.due : null,
    due_rule_code: r.dueRule,
    tags: [
      ...(r.extended ? ["ext"] : []),
      ...(DRAFT_K1.has(r.client) && !r.label.endsWith(":2") ? ["draft_k1"] : []),
    ],
    issues: r.issues,
    signers: (envelope?.signers ?? []).map((s) => ({ name: s.name, signed: s.signed })),
  };
}

const ZERO: TaxReturnSummaryOut = {
  tax_year: TAX_YEAR + 1,
  total: 0,
  open: 0,
  done: 0,
  extended: 0,
  tiles: TY2025_SUMMARY.tiles.map((t) => ({ ...t, count: 0 })),
  offices: [],
};

function dueOf(r: TaxReturnRowOut): string {
  return r.extended_due_on ?? r.original_due_on ?? "9999-12-31";
}

function rows(query: URLSearchParams): TaxReturnRowOut[] {
  const year = Number(query.get("tax_year") ?? TAX_YEAR);
  if (year !== TAX_YEAR) return [];
  const status = new Set(query.getAll("status"));
  const offices = new Set(query.getAll("office"));
  const q = query.get("q")?.trim().toLowerCase();
  const found = TAX_RETURNS.map(rowOf).filter(
    (r) =>
      (status.size === 0 || status.has(r.status)) &&
      (offices.size === 0 || (r.office_id !== null && offices.has(r.office_id))) &&
      (q === undefined || q === "" || r.client_name.toLowerCase().includes(q)),
  );
  const byClient = query.get("sort") === "client";
  const grouped = query.get("group_by") === "office";
  return found.sort((a, b) => {
    if (grouped && a.office_id !== b.office_id)
      return (a.office_id ?? "") < (b.office_id ?? "") ? -1 : 1;
    if (!byClient && dueOf(a) !== dueOf(b)) return dueOf(a) < dueOf(b) ? -1 : 1;
    return a.client_name.localeCompare(b.client_name);
  });
}

const TABS = ["overview", "intake", "review", "issues", "activity"];

/** The return's `ReturnFrame` record and TAX-02 overview: the variant's when it names this
 * return (TAX-02 a–e), otherwise the row alone with empty bands (no invented overview rows). */
function frameOf(
  id: string,
  variant: OverviewVariant | undefined,
): { record: TaxReturnRecordOut; overview: TaxReturnOverviewOut } | undefined {
  const seed = TAX_RETURNS.find((r) => r.id === id);
  if (seed === undefined) return undefined;
  const base = rowOf(seed);
  const v = variant === undefined ? undefined : OVERVIEWS[variant];
  const mine = v !== undefined && v.row.client === seed.client && !seed.label.endsWith(":2");
  const row: TaxReturnRowOut = mine ? { ...base, ...v.row } : base;
  const record: TaxReturnRecordOut = {
    row,
    engagement_id: stableId(`engagement:${seed.label}`),
    work_item_id: stableId(`work-item:${seed.label}`),
    approval_policy_version_id: null,
    engine_url: null,
    ...(mine
      ? v.record
      : {
          tabs: TABS.map((tab) => ({ tab, count: null })),
          card_detail: seed.office,
          engine_return_id: null,
          allowed_actions: ["tax_return.read", "tax_return.assign"],
        }),
  };
  const overview: TaxReturnOverviewOut = mine
    ? { return_id: id, ...v.overview }
    : {
        return_id: id,
        ladder: [],
        engine_version: null,
        engine_summary: [],
        open_issues: seed.issues ?? 0,
        k1_dependencies: [],
        consent_ok: null,
        allowed_actions: record.allowed_actions,
      };
  return { record, overview };
}

/** The board's reads and writes; `variant` picks TAX-02's artboard for the return it names. */
export function taxReturnHandlers(variant?: OverviewVariant): Record<string, FixtureHandler> {
  return {
    "GET /v1/tax-returns/{return_id}": ({ params }) => {
      const frame = frameOf(params.return_id ?? "", variant);
      return frame === undefined ? json({ detail: "not_found" }, 404) : json(frame.record);
    },
    "GET /v1/tax-returns/{return_id}/overview": ({ params }) => {
      const frame = frameOf(params.return_id ?? "", variant);
      return frame === undefined ? json({ detail: "not_found" }, 404) : json(frame.overview);
    },
    "POST /v1/tax-returns/{return_id}/assignments": ({ params }) => {
      const frame = frameOf(params.return_id ?? "", variant);
      return frame === undefined ? json({ detail: "not_found" }, 404) : json(frame.record);
    },
    "GET /v1/tax-returns/summary": ({ query }) =>
      json(Number(query.get("tax_year") ?? TAX_YEAR) === TAX_YEAR ? TY2025_SUMMARY : ZERO),
    "GET /v1/tax-returns": ({ query }) => {
      const sort = query.get("sort");
      if (sort !== null && sort !== "client" && sort !== "extended_due") {
        return json({ detail: "validation" }, 422);
      }
      const items = rows(query);
      return json({ items, next_cursor: null, total: items.length });
    },
    "POST /v1/tax-returns:bulk-assign": ({ body }) => {
      const ids = (body as { return_ids?: string[] } | null)?.return_ids ?? [];
      return json({ assigned: ids.length, refused: [] });
    },
  };
}
