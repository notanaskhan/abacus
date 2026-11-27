// TXP-13 fixture scenarios (T-06-T23, DEC-5636; docs/screens/TXP-13.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// a–c serve the E0 seed until their screen tasks land. T-06-T45 (DEC-5937): d is Granite Peak's
// FY2026 Form 1120 with its hand-off landing from the Python slice (`seed/aud38.ts`).
import type { TaxReturnRecordOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json, never } from "../../app-core/fixture-mode";
import { seededReturnRecord } from "../handlers/tax-returns";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { AUD38_LANDING, AUD38_TARGET } from "../seed/aud38";
import { stableId } from "../seed/prng";
import exported from "../seed/scenario.txp13-frames.json";
import { capabilitiesFor } from "../seed/shell";
import { TAX_RETURNS } from "../seed/tax";

export const TXP13_RETURN = AUD38_TARGET;
const E0 = seedScenario();

// T-06-T52 (DEC-6036): frames a to c3 read the Python scenario's lines
// (`seed/scenario.txp13-frames.json`, `make fixtures`, never hand written).
type Frame = "a" | "b" | "b2" | "c" | "c2" | "c3";
const FORM: Record<Frame, ["1120s" | "1120" | "990", string]> = {
  a: ["1120s", exported.a.client],
  b: ["1120", exported.b.client],
  b2: ["1120", exported.b.client],
  c: ["990", exported.c.client],
  c2: ["990", exported.c.client],
  c3: ["990", exported.c.client],
};
export const FRAME_RETURN: Record<Frame, string> = {
  a: stableId("tax-return:bluestem:2025:1120s"),
  b: stableId("tax-return:ashford:2025:1120"),
  b2: stableId("tax-return:ashford:2025:1120"),
  c: stableId("tax-return:lakeshore:2025:990"),
  c2: stableId("tax-return:lakeshore:2025:990"),
  c3: stableId("tax-return:lakeshore:2025:990"),
};

function frameRecord(frame: Frame): TaxReturnRecordOut {
  const [form, client] = FORM[frame];
  const base = (seededReturnRecord(client) ??
    seededReturnRecord(TAX_RETURNS[0]?.client ?? "")) as TaxReturnRecordOut;
  return {
    ...base,
    row: {
      ...base.row,
      id: FRAME_RETURN[frame],
      client_name: client,
      form,
      tax_year: 2025,
      status: frame === "a" ? "accepted" : frame.startsWith("c") ? "gathering" : "in_review",
      fiscal_year_end: frame.startsWith("c") ? exported.c.fiscal_year_end : null,
    },
  };
}

function provision(frame: Frame) {
  const b = exported.b;
  const items = b.recon_items.map((r) => ({
    item_id: stableId(`rate-recon:ashford:${r.key}`),
    description: r.description,
    amount: r.amount,
    rate_effect: r.rate_effect,
    classification: r.classification as "rate" | "permanent",
  }));
  const off = frame === "b2";
  return {
    view: "provision" as const,
    current: b.current,
    deferred: b.deferred,
    total: b.total,
    effective_rate: b.effective_rate,
    rate_reconciliation_tally: off ? ("off" as const) : ("tie" as const),
    unclassified: off ? exported.b2_unclassified : null,
    pretax_book_income: b.pretax_book_income,
    permanent_total: b.permanent_total,
    temporary_total: b.temporary_total,
    taxable_income: b.taxable_income,
    blended_rate: b.blended_rate,
    recon_items: off
      ? [
          ...items,
          {
            item_id: stableId("rate-recon:ashford:unclassified_1"),
            description: "Unclassified difference",
            amount: exported.b2_unclassified,
            rate_effect: null,
            classification: "unclassified" as const,
          },
        ]
      : items,
    deferred_items: b.deferred_items.map((d) => ({ ...d, kind: d.kind as "dta" | "dtl" })),
  };
}

function at(state: Frame, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      const a = exported.a;
      const c = exported.c;
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), who ?? persona);
          return json({ ...base, flags: { ...base.flags, "tax.other_entity_workpapers": true } });
        },
        "GET /v1/tax-returns/{return_id}": () => json(frameRecord(state)),
        "GET /v1/tax-returns/{return_id}/handoff": () => json({}),
        "GET /v1/tax-returns/{return_id}/schedules/aaa": () =>
          json({
            aaa: a.aaa,
            pti: "0",
            e_and_p: "0",
            oaa: "0",
            shareholder_pcts: a.shareholders.map((h) => h.pct),
            locked: true,
            lines: a.lines.map((l) => ({ ...l, pti: "0", e_and_p: "0", oaa: "0" })),
            shareholders: a.shareholders,
          }),
        "GET /v1/tax-returns/{return_id}/provision": () => json(provision(state)),
        "POST /v1/tax-returns/{return_id}/provision/items/{item_id}/explain": () =>
          json({ issue_id: stableId("issue:ashford:unclassified_1") }, 202),
        "GET /v1/tax-returns/{return_id}/functional-expenses": () =>
          state === "c3"
            ? never()
            : json({
                view: "part_ix",
                program: c.program,
                management: c.management,
                fundraising: c.fundraising,
                total: c.total,
                program_ratio: c.program_ratio,
                public_support: c.public_support,
                lines: c.lines,
              }),
      };
    },
  };
}

function record(): TaxReturnRecordOut {
  const base = seededReturnRecord(TAX_RETURNS[0]?.client ?? "") as TaxReturnRecordOut;
  return {
    ...base,
    row: {
      ...base.row,
      client_name: "Granite Peak Outdoor Supply, Inc.",
      form: "1120",
      tax_year: 2025,
    },
  };
}

function granite(state: string, landed: boolean): Scenario {
  return {
    state,
    persona: "leo-wong",
    clock: "2026-11-09T11:00:00-06:00",
    handlers: {
      ...E0.handlers,
      // T-06-T52: TXP-13 gates frame d on `tax.tb_handoff` itself (the route no longer does).
      "GET /v1/me/capabilities": ({ persona: who }: { persona?: string | undefined }) => {
        const base = capabilitiesFor(getSeed(), who ?? "leo-wong");
        return json({
          ...base,
          flags: { ...base.flags, "tax.tb_handoff": true, "tax.other_entity_workpapers": true },
        });
      },
      "GET /v1/tax-returns/{return_id}": () => json(record()),
      "GET /v1/tax-returns/{return_id}/handoff": () => json(landed ? AUD38_LANDING : {}),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-14T09:24:00-05:00"), // 1120-S · AAA (Bluestem, Accepted, read-only) · `bluestem-1120s`
  b: at("b", "samuel-ito", "2026-09-14T09:24:00-05:00"), // 1120 · ASC 740 provision (Ashford 2,257,200) · `ashford-1120`
  b2: at("b2", "samuel-ito", "2026-09-14T09:24:00-05:00"), // Exception · unclassified difference (off 1,200) · `ashford-unclassified`
  c: at("c", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Part IX (Lakeshore 4,014,000) · `lakeshore-990`
  c2: at("c2", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Allocation basis · `lakeshore-990`
  c3: at("c3", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // 990 · Building (skeleton) · `lakeshore-990-building`
  d: granite("d", true), // 1120 · from the audit (Granite Peak) · `granite-peak-1120`
});

export type Txp13State = keyof typeof scenarios;
/** T-06-T45: Granite Peak's 1120 with no hand-off (no artboard; the screen's empty case). */
export const noHandoff: Scenario = granite("none", false);
