// CLS-08 fixture scenarios (C-02-T15, DEC-5624; C-02-T23, DEC-5707; handoff CLS-08): Copperleaf
// August 2026 close package, released by Priya Raman. Each artboard's persona and clock (CDT until
// Sun Nov 1, 2026; CST after). The statements are the Python scenario's
// (`seed/scenario.cls08-package.json`, `make fixtures`, never hand written); each state sets only
// what the artboard changes: b drafting, c the three blockers of 9:24 AM, d released at 4:25 PM,
// e approved by Tess Moreno at 8:42 AM on Sep 15, f the SSARS 27 route (no legend), g the "No"
// answer (a standalone engagement).
import type { DeliveryPackageOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import exported from "../seed/scenario.cls08-package.json";
import { CLOSE_IDS } from "../seed/closes";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
export const CLS08_CLOSE_ID = CLOSE_IDS.august;
const ALL_ON = ["balance_sheet", "income_statement", "cash_flows", "commentary"] as const;

function pkg(state: string): DeliveryPackageOut {
  const base: DeliveryPackageOut = {
    close_id: CLS08_CLOSE_ID,
    status: "draft",
    version_no: 2,
    route: "ar_c_70_preparation",
    legend: exported.legend,
    sections: [...ALL_ON],
    cas_answer: true,
    balance_sheet: exported.balance_sheet,
    income_statement: exported.income_statement,
    commentary: exported.commentary,
    preconditions: [],
    content_hash: "0".repeat(64),
    version: 2,
  };
  switch (state) {
    case "b":
      return { ...base, status: "drafting" };
    case "c":
      return {
        ...base,
        preconditions: [
          { blocker: "accounts_unreconciled", done: 9, of: 21 },
          { blocker: "issues_open", done: 7 },
          { blocker: "entries_unposted" },
        ],
      };
    case "d":
      return { ...base, status: "released", released_at: exported.released_at };
    case "e":
      return {
        ...base,
        status: "approved_by_client",
        released_at: exported.released_at,
        client_approved_at: exported.client_approved_at,
      };
    case "f":
      return { ...base, route: "cas_by_product", legend: null };
    case "g":
      return { ...base, route: "standalone_letter", legend: null, cas_answer: false };
    default:
      return base;
  }
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
            flags: {
              ...base.flags,
              "closes.engine": true,
              "adjustments.posting": true,
              "closes.delivery": true,
            },
          });
        },
        "GET /v1/closes/{close_id}/package": () => json(pkg(state)),
        "PATCH /v1/closes/{close_id}/package": () => json(pkg(state)),
        "PATCH /v1/closes/{close_id}/package/commentary": ({ body }: { body?: unknown }) =>
          json({ ...pkg(state), commentary: (body as { doc?: string } | undefined)?.doc ?? null }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "priya-raman", "2026-09-14T16:10:00-05:00"),
  a2: at("a2", "priya-raman", "2026-09-14T16:10:00-05:00"),
  b: at("b", "priya-raman", "2026-09-14T16:10:00-05:00"),
  c: at("c", "priya-raman", "2026-09-14T16:10:00-05:00"),
  d: at("d", "priya-raman", "2026-09-14T16:25:00-05:00"),
  e: at("e", "priya-raman", "2026-09-14T08:42:00-05:00"),
  f: at("f", "priya-raman", "2026-09-14T16:10:00-05:00"),
  g: at("g", "priya-raman", "2026-09-14T16:10:00-05:00"),
});

export type Cls08State = keyof typeof scenarios;
export const INITIAL: Cls08State = "a";
