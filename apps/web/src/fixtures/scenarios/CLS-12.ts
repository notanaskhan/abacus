// CLS-12 fixture scenarios (C-02-T15, DEC-5624; C-02-T48, DEC-6031; handoff CLS-12): the December
// 2026 close's tax hand-off, by Priya Raman. Each artboard's persona and clock (CDT until Sun Nov
// 1, 2026; CST after). The sheet's facts are the Python scenario's
// (`seed/scenario.cls12-handoff.json`, `make fixtures`, never hand written) in C-02-T39's read
// shape: a ready (TB v1 on the close locked Jan 11, 2027), b the August close (not available yet),
// c and c2 handed off at 2:15 PM (the toast, then TXP-02's provenance banner), d the close
// reopened on Jan 20 (handing off again supersedes TB v1).
import type { DeliveryHandoffOut } from "@abacus/api-client";
import {
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { copperleafAugust } from "../seed/closes";
import { stableId } from "../seed/prng";
import exported from "../seed/scenario.cls12-handoff.json";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
export const CLS12_DECEMBER_ID = stableId("close:copperleaf:2026-12");
const RETURN_ID = stableId("tax-return:copperleaf:2026-1120s");

const LABELS: Record<string, string> = {
  fixed_assets: "Fixed asset register",
  prepaid_expenses: "Prepaid insurance",
  deferred_revenue: "Deferred revenue",
  shareholder_distributions: "Shareholder distributions",
  accrued_liabilities: "Accrued payroll at Dec 31",
};

export function cls12Handoff(state: string): DeliveryHandoffOut {
  if (state === "b") {
    return { status: "not_available", reason: "Available after the December 2026 close locks" };
  }
  const handedOff = state === "c" || state === "c2";
  return {
    status: handedOff ? "handed_off" : "ready",
    tb_version: exported.tb_version,
    locked_at: exported.locked_on,
    balanced: true,
    target_return_id: RETURN_ID,
    target_form: exported.target_form,
    target_tax_year: exported.target_tax_year,
    target_engine: exported.engine,
    target_preparer: exported.tax_team.preparer,
    target_reviewer: exported.tax_team.reviewer,
    schedules: exported.schedules.map((s) => ({
      key: s.key,
      label: LABELS[s.key] ?? s.key,
      included: true,
      figures: s.figures,
    })),
    items: exported.items.map((title, i) => ({
      issue_id: stableId(`close-issue:copperleaf:2026-12:${String(i)}`),
      title,
      resolved: true,
      create_tax_issue: true,
    })),
    superseded_on_next: state === "d",
    version: 3,
    ...(handedOff || state === "d"
      ? { handed_off_by: exported.handed_off_by, handed_off_at: exported.handed_off_at }
      : {}),
    ...(state === "d" ? { reopened_at: `${exported.reopened_on}T09:00:00-06:00` } : {}),
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
            flags: {
              ...base.flags,
              "closes.engine": true,
              "adjustments.posting": true,
              "closes.tax_handoff": true,
            },
          });
        },
        "GET /v1/closes/{close_id}/tax-handoff": () => json(cls12Handoff(state)),
        // The December close under the sheet: locked Jan 11, 2027 (CLS-12's background).
        "GET /v1/closes/{close_id}": () =>
          json({
            ...copperleafAugust(),
            close_id: CLS12_DECEMBER_ID,
            period: "2026-12",
            status: "locked",
            open_issues: 0,
            accounts_reconciled: 21,
            accounts_total: 21,
          }),
        "POST /v1/closes/{close_id}/tax-handoff": ({ body }: FixtureRequest) =>
          json(
            {
              handoff_id: stableId("tax-handoff:copperleaf:2026-12:1"),
              tb_version: exported.tb_version,
              tax_issues_created: ((body as { items?: string[] } | null)?.items ?? []).length,
            },
            202,
          ),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "priya-raman", "2027-01-12T14:15:00-06:00"),
  b: at("b", "priya-raman", "2026-09-14T09:24:00-05:00"),
  c: at("c", "priya-raman", "2027-01-12T14:15:00-06:00"),
  c2: at("c2", "priya-raman", "2027-01-12T14:15:00-06:00"),
  d: at("d", "priya-raman", "2027-01-20T09:24:00-06:00"),
});

export type Cls12State = keyof typeof scenarios;
export const INITIAL: Cls12State = "a";
