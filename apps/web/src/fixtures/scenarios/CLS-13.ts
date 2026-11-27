// CLS-13 fixture scenarios (C-02-T15, DEC-5624; C-02-T47, DEC-6030; handoff CLS-13): Copperleaf's
// 1099 tracking and January filing, seen by Raj Malhotra. Each artboard's persona and clock (CDT
// until Sun Nov 1, 2026; CST after). The rows are the Python scenario's
// (`seed/scenario.cls13-tracker.json`, `make fixtures`, never hand written) in C-02-T45's read
// shape; each state sets only what the artboard changes: b the W-9 request drawer open
// (`?w9=1`), c Elena Ruiz Design's row expanded (`?vendor=`), d January with the December close
// locked (Approve open), d2 the batch filed through IRIS, e tax year 2025 (filed before the ledger
// connected), f a client whose ledger never synced.
import type { DeliveryInformationReturnsOut, DeliveryVendorRowOut } from "@abacus/api-client";
import {
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { entityIdOf, slugOfClient } from "../seed/clients";
import { stableId } from "../seed/prng";
import exported from "../seed/scenario.cls13-tracker.json";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const SLUG = slugOfClient(exported.client);
export const CLS13_CLIENT_ID = stableId(`client:${SLUG}`);
export const CLS13_ENTITY_ID = entityIdOf(SLUG, exported.client);
export const vendorIdOf = (name: string): string => stableId(`vendor-1099:${SLUG}:${name}`);
export const ELENA_ID = vendorIdOf("Elena Ruiz Design");

type Row = DeliveryVendorRowOut;
type Payment = NonNullable<Row["payments"]>[number];

function row(r: (typeof exported.rows)[number], filed: boolean): Row {
  return {
    vendor_id: vendorIdOf(r.display_name),
    display_name: r.display_name,
    entity_type: r.entity_type as Row["entity_type"],
    is_attorney: r.is_attorney,
    reportability: r.reportability as Row["reportability"],
    form: r.form as "nec" | "misc" | null,
    box: r.box,
    amount: r.amount,
    tin_last4: r.tin_last4,
    tin_kind: r.tin_kind as "ssn" | "ein" | null,
    w9_status: r.w9_status as Row["w9_status"],
    w9_requested_at: r.w9_requested_on === null ? null : `${r.w9_requested_on}T00:00:00-05:00`,
    tin_mismatch_on: r.tin_mismatch_on,
    backup_withholding: r.backup_withholding as "none" | "watch" | "started",
    version: 1,
    filed: filed && r.reportability === "reportable",
    payments: r.payments.map((p): Payment => ({
      method: p.method as Payment["method"],
      amount: p.amount,
      counted: p.counted,
    })),
  };
}

const THRESHOLD_2026 =
  "threshold $2,000 for 2026 payments (rules table) · card and payment-app payments excluded (reported on Form 1099-K)";
const DUE_2026 = "Recipient copies and 1099-NEC to the IRS due Feb 1, 2027 · IRIS";

export function cls13Tracker(state: string, year: number): DeliveryInformationReturnsOut {
  if (state === "f") {
    return {
      tax_year: year,
      vendors_paid: 0,
      reportable: 0,
      requested: 0,
      w9_mismatches: 0,
      filed: 0,
      threshold_rule: THRESHOLD_2026,
      due_rule: DUE_2026,
      items: [],
      batch_status: "not_started",
    };
  }
  if (year === exported.prior.tax_year) {
    const items: Row[] = exported.prior.rows.map((r) => ({
      vendor_id: vendorIdOf(r.display_name),
      display_name: r.display_name,
      entity_type: r.entity_type as Row["entity_type"],
      is_attorney: r.is_attorney,
      reportability: "reportable",
      form: r.form as "nec" | "misc" | null,
      box: r.box,
      amount: r.amount,
      tin_last4: r.tin_last4,
      tin_kind: r.tin_kind as "ssn" | "ein" | null,
      w9_status: "on_file",
      version: 1,
      filed: true,
    }));
    return {
      tax_year: year,
      vendors_paid: 0,
      reportable: items.length,
      requested: 0,
      w9_mismatches: 0,
      filed: items.length,
      threshold_rule: `threshold $600 for ${String(year)} payments (rules table) · card and payment-app payments excluded (reported on Form 1099-K)`,
      due_rule: "Recipient copies and 1099-NEC to the IRS due Feb 2, 2026 · IRIS",
      items,
      batch_status: "accepted",
      payments_synced: false,
      filed_on: exported.prior.accepted_on,
      accepted_at: `${exported.prior.accepted_on}T12:00:00-06:00`,
    };
  }
  const filed = state === "d2";
  const items = exported.rows.map((r) => row(r, filed));
  return {
    tax_year: year,
    ...exported.tiles,
    filed: filed ? items.filter((i) => i.filed).length : 0,
    threshold_rule: THRESHOLD_2026,
    due_rule: DUE_2026,
    items,
    batch_status: filed ? "filed_iris" : "not_started",
    approval_open: state === "d" || state === "d2",
    approval_target_on: exported.december_close_due,
    ...(filed ? { filed_on: "2027-01-28" } : {}),
  };
}

function at(state: string, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          return json({
            ...base,
            flags: { ...base.flags, "closes.engine": true, "adjustments.posting": true },
          });
        },
        "GET /v1/client-entities/{client_entity_id}/information-returns": ({
          query,
        }: FixtureRequest) => json(cls13Tracker(state, Number(query.get("tax_year") ?? "2026"))),
        "POST /v1/client-entities/{client_entity_id}/w9-requests": ({ body }: FixtureRequest) => {
          const ids = (body as { vendor_ids?: string[] } | null)?.vendor_ids ?? [];
          return json(
            {
              request_id: stableId(`w9-request:${SLUG}:${ids.join(",")}`),
              request_item_ids: ids.map((v) => stableId(`request-item:w9:${v}`)),
              sent_at: clock,
            },
            201,
          );
        },
        "POST /v1/vendors/{vendor_id}/backup-withholding": ({ params }: FixtureRequest) =>
          json({ vendor_id: params["vendor_id"], backup_withholding: "started" }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  b: at("b", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  c: at("c", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  d: at("d", "raj-malhotra", "2027-01-26T09:24:00-06:00"),
  d2: at("d2", "raj-malhotra", "2027-01-28T09:24:00-06:00"),
  e: at("e", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
  f: at("f", "raj-malhotra", "2026-09-14T09:24:00-05:00"),
});

export type Cls13State = keyof typeof scenarios;
export const INITIAL: Cls13State = "a";
