// AUD-06 Trial balance & leadsheets: one fixture scenario per artboard a–h plus the five added
// states (A-02-T05; A-02 §5.3; handoff AUD-06 README, spec.md and revision.md R2). The C9 v1 reads
// answer from seed/aud06.ts (the server's shapes; the fixtures compute what the server computes):
//
//   a  hannah-leclerc  Mon Sep 14, 2:30 PM  Northwind PY2025 v1 adopted 10:02 AM, three ties
//   b  hannah-leclerc  2:30 PM (9:26 AM state)  the agent's draft: outlined agent ticks, no initials
//   c  hannah-leclerc  2:30 PM  BrokerWindow EOY 1,606,560.00: "off 1,560.00", issue linked
//   d  hannah-leclerc  Tue Oct 6, 2:30 PM  Final layer with AJE-1 (48,600.00), net assets 16,861,000.00
//   e  hannah-leclerc  2:30 PM  the Investments leadsheet (Δ and Δ% from the server)
//   f  hannah-leclerc  2:30 PM  a's data with `?ov=signoff:…:L2` (SHL-12 mounts with P-04-T48)
//   g  caleb-dunn      Mon Sep 14, 4:05 PM (E1)  Harlow & Pike Manufacturing Interim 8/31/2026,
//                      whole dollars, debits = credits 86,000,000, net income 3,400,000
//   h  hannah-leclerc  Mon Nov 9, 10:15 AM CST  Granite Peak FY2026 Final (Hand off to tax planned)
//   empty        simone-baptiste  E0  Granite Peak before adoption: one pulled snapshot, no TB
//   newer        simone-baptiste  E0  Granite Peak v1 with one newer pull (2 lines changed)
//   loading      simone-baptiste  E0  the TB list never answers
//   error        simone-baptiste  E0  the TB list answers 500
//   not_allowed  cole-hart        E0  walled from Granite Peak: every read answers 404 (INV-3)
//
// They live under fixtures/ (dev and test only); src/screens/AUD-06/scenarios.ts re-exports them.

import type {
  CapabilitiesOut,
  TbLayerViewOut,
  TbLeadsheetAreaOut,
  TieOutCheckOut,
  TrialBalancesOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { auditHandlers, northwindAuditId } from "../handlers/audits";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";
import { DOCUMENTS } from "../seed/trust";
import {
  GRANITE_FY2026,
  GRANITE_FY2026_REPULL,
  GRANITE_HAND_OFF,
  GRANITE_TB,
  HARLOW_ENGAGEMENT,
  HARLOW_ENTITIES,
  aud06Checks,
  aud06Citations,
  aud06Newer,
  aud06a,
  aud06b,
  aud06c,
  aud06d,
  aud06e,
  aud06g,
  aud06h,
  graniteTrialBalance,
  harlowChecks,
  snapshotOf,
} from "../seed/aud06";
import { stableId } from "../seed/prng";

const E0 = seedScenario();
const seed = getSeed();

function engagementOf(entity: string): string {
  const found = seed.engagements.find((e) => e.client_entity_name === entity);
  if (found === undefined) throw new Error(`the seed has no ${entity} engagement`);
  return found.id;
}

export const NORTHWIND_ENGAGEMENT = engagementOf("Northwind Robotics 401(k) Plan");
export const GRANITE_ENGAGEMENT = engagementOf("Granite Peak Outdoor Supply, Inc.");
export { HARLOW_ENGAGEMENT };
/** Northwind's PY2025 audit work item: the AUD-02 cockpit a–f open AUD-06 in (A-02-T09). */
export const NORTHWIND_AUDIT = northwindAuditId(seed);

const NOT_FOUND = { detail: "not_found" };
const LAYER_UNAVAILABLE = { detail: "layer_unavailable" };

const P = "/v1/engagements/{engagement_id}/trial-balances";

interface TbFixture {
  engagementId: string;
  list: TrialBalancesOut;
  view?: TbLayerViewOut;
  checks?: TieOutCheckOut[];
  leadsheet?: TbLeadsheetAreaOut;
  candidates?: TrialBalancesOut["snapshots"];
  /** Personas a wall keeps out (INV-3: a 404, no hint). */
  walled?: readonly string[];
}

/** The C9 v1 reads AUD-06 makes, over one engagement's fixture. */
export function tbHandlers(f: TbFixture): Record<string, FixtureHandler> {
  const mine = (r: FixtureRequest): boolean =>
    r.params.engagement_id === f.engagementId && !(f.walled ?? []).includes(r.persona ?? "");
  const tb = (r: FixtureRequest): boolean =>
    mine(r) && f.view !== undefined && r.params.tb_id === f.view.trial_balance_id;
  return {
    [`GET ${P}`]: (r) => (mine(r) ? json(f.list) : json(NOT_FOUND, 404)),
    [`GET ${P}/{tb_id}/layers/{layer}`]: (r) => {
      if (!tb(r) || f.view === undefined) return json(NOT_FOUND, 404);
      const layer = r.params.layer ?? "";
      if (!(f.view.layers_available as readonly string[]).includes(layer)) {
        return json(LAYER_UNAVAILABLE, 409);
      }
      return json(f.view);
    },
    [`GET ${P}/{tb_id}/checks`]: (r) => (tb(r) ? json(f.checks ?? []) : json(NOT_FOUND, 404)),
    [`GET ${P}/{tb_id}/leadsheets/{area}`]: (r) =>
      tb(r) && f.leadsheet !== undefined && r.params.area === f.leadsheet.area
        ? json(f.leadsheet)
        : json(NOT_FOUND, 404),
    [`GET ${P}/{tb_id}/candidates`]: (r) =>
      tb(r) ? json(f.candidates ?? []) : json(NOT_FOUND, 404),
    // A-02-T24: the live actions. Adoption and re-version answer 201 (the screen reads again);
    // Open in Excel answers a file named as the server names it.
    [`POST ${P}`]: (r) => (mine(r) ? json({}, 201) : json(NOT_FOUND, 404)),
    [`POST ${P}/{tb_id}/versions`]: (r) => (tb(r) ? json({}, 201) : json(NOT_FOUND, 404)),
    [`GET ${P}/{tb_id}/export.xlsx`]: (r) =>
      tb(r)
        ? new Response(new Blob(["PK"]), {
            status: 200,
            headers: {
              "Content-Type": XLSX,
              "Content-Disposition": `attachment; filename="trial-balance-v${r.query.get("version") ?? "1"}-${r.query.get("layer") ?? "unadjusted"}.xlsx"`,
            },
          })
        : json(NOT_FOUND, 404),
  };
}

const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

/** The scenario instants (CT; Nov 9 is CST). */
export const AUD06_CLOCKS = {
  default: "2026-09-14T14:30:00-05:00",
  oct6: "2026-10-06T14:30:00-05:00",
  e1: "2026-09-14T16:05:00-05:00",
  nov9: "2026-11-09T10:15:00-06:00",
} as const;

function northwindList(view: TbLayerViewOut): TrialBalancesOut {
  return {
    trial_balances: [
      {
        id: view.trial_balance_id,
        label: view.label,
        display_unit: view.display_unit,
        period_start: view.period_start,
        period_end: view.period_end,
        current_version_no: view.current_version_no,
      },
    ],
    snapshots: [],
  };
}

/** The cockpit's flag, as AUD-02's scenarios grant it, and the C9 v1 workpaper's (DEC-314). */
function cockpitCapabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    capabilities: [...base.capabilities, "engagement.read_metadata"],
    flags: { ...base.flags, "audits.cockpit": true, "ledger.tb_workpaper": true },
  };
}

/** Northwind's frames are the AUD-02 cockpit with the Trial Balance row open (A-02-T09): the
 * cockpit's reads, the Harborline document and the citation behind each cited line. */
function northwind(
  state: string,
  view: TbLayerViewOut,
  extra: Partial<TbFixture> = {},
  clock: string = AUD06_CLOCKS.default,
): Scenario {
  return {
    state,
    persona: "hannah-leclerc",
    clock,
    handlers: {
      ...E0.handlers,
      ...trustHandlers({ documents: DOCUMENTS, citations: aud06Citations(view) }),
      ...auditHandlers(seed, "run"),
      "GET /v1/me/capabilities": ({ persona }) => json(cockpitCapabilities(persona)),
      ...tbHandlers({
        engagementId: NORTHWIND_ENGAGEMENT,
        list: northwindList(view),
        view,
        checks: aud06Checks(view),
        ...extra,
      }),
    },
  };
}

const PULLED = "2026-09-14T09:00:00-05:00";
const REPULLED = "2026-09-14T09:20:00-05:00";
const PULL_1 = stableId("snapshot:granite-peak:fy2026:1");
const PULL_2 = stableId("snapshot:granite-peak:fy2026:2");

function granite(state: string, persona: string, f: Partial<TbFixture>, clock?: string): Scenario {
  return {
    state,
    persona,
    clock: clock ?? seed.clock.instant,
    handlers: {
      ...E0.handlers,
      ...tbHandlers({
        engagementId: GRANITE_ENGAGEMENT,
        list: { trial_balances: [], snapshots: [] },
        ...f,
      }),
    },
  };
}

const graniteList = (snapshots: TrialBalancesOut["snapshots"] = []): TrialBalancesOut => ({
  trial_balances: [graniteTrialBalance()],
  snapshots,
});

const harlow = aud06g();
const viewA = aud06a(NORTHWIND_ENGAGEMENT);
const viewC = aud06c(NORTHWIND_ENGAGEMENT);
const viewH = aud06h(GRANITE_ENGAGEMENT);
const viewNewer = aud06Newer(GRANITE_ENGAGEMENT);

export const scenarios = defineScenarios({
  a: northwind("a", viewA),
  b: northwind("b", aud06b(NORTHWIND_ENGAGEMENT)),
  c: northwind("c", viewC, { checks: aud06Checks(viewC) }),
  d: northwind("d", aud06d(NORTHWIND_ENGAGEMENT), {}, AUD06_CLOCKS.oct6),
  e: northwind("e", viewA, { leadsheet: aud06e(viewA.trial_balance_id) }),
  f: northwind("f", viewA),
  g: {
    state: "g",
    persona: "caleb-dunn",
    clock: AUD06_CLOCKS.e1,
    handlers: {
      ...E0.handlers,
      ...tbHandlers({
        engagementId: HARLOW_ENGAGEMENT,
        list: {
          trial_balances: [
            {
              id: harlow.trial_balance_id,
              label: harlow.label,
              display_unit: harlow.display_unit,
              period_start: harlow.period_start,
              period_end: harlow.period_end,
              current_version_no: 1,
            },
          ],
          snapshots: [],
        },
        view: harlow,
        checks: harlowChecks(harlow),
      }),
    },
  },
  h: granite(
    "h",
    "hannah-leclerc",
    { list: graniteList(), view: viewH, checks: [] },
    AUD06_CLOCKS.nov9,
  ),
  empty: granite("empty", "simone-baptiste", {
    list: { trial_balances: [], snapshots: [snapshotOf(PULL_1, GRANITE_FY2026, PULLED)] },
  }),
  newer: granite("newer", "simone-baptiste", {
    list: graniteList(),
    // Simone may adopt the newer pull as v2 (A-02-T24: "Use v2…").
    view: {
      ...viewNewer,
      allowed_actions: [...(viewNewer.allowed_actions ?? []), "trial_balance.adopt"],
    },
    checks: [],
    candidates: [snapshotOf(PULL_2, GRANITE_FY2026_REPULL, REPULLED, GRANITE_FY2026)],
  }),
  loading: {
    ...granite("loading", "simone-baptiste", {}),
    handlers: {
      ...granite("loading", "simone-baptiste", {}).handlers,
      [`GET ${P}`]: () => never(),
    },
  },
  error: {
    ...granite("error", "simone-baptiste", {}),
    handlers: {
      ...granite("error", "simone-baptiste", {}).handlers,
      [`GET ${P}`]: () => json({}, 500),
    },
  },
  not_allowed: granite("not_allowed", "cole-hart", {
    list: graniteList(),
    view: viewNewer,
    walled: ["cole-hart"],
  }),
});

/** What each artboard opens on: the tab, the layer and the overlay (A-02-T09/T14 read these). */
export const OPENS: Readonly<
  Record<
    keyof typeof scenarios,
    {
      engagementId: string;
      tbId: string | null;
      tab: "trial_balance" | "leadsheets";
      layer: TbLayerViewOut["layer"];
      area?: string;
      selected?: string;
      ov?: string;
      /** Facts for planned controls (the entity strip, Hand off to tax…): dev builds only. */
      planned?: { entities?: readonly string[]; entity?: string; handOffToTax?: string };
    }
  >
> = {
  a: {
    engagementId: NORTHWIND_ENGAGEMENT,
    tbId: viewA.trial_balance_id,
    tab: "trial_balance",
    layer: "unadjusted",
    selected: "1130",
  },
  b: {
    engagementId: NORTHWIND_ENGAGEMENT,
    tbId: viewA.trial_balance_id,
    tab: "trial_balance",
    layer: "unadjusted",
  },
  c: {
    engagementId: NORTHWIND_ENGAGEMENT,
    tbId: viewA.trial_balance_id,
    tab: "trial_balance",
    layer: "unadjusted",
  },
  d: {
    engagementId: NORTHWIND_ENGAGEMENT,
    tbId: viewA.trial_balance_id,
    tab: "trial_balance",
    layer: "final",
  },
  e: {
    engagementId: NORTHWIND_ENGAGEMENT,
    tbId: viewA.trial_balance_id,
    tab: "leadsheets",
    layer: "unadjusted",
    area: "Investments",
  },
  f: {
    engagementId: NORTHWIND_ENGAGEMENT,
    tbId: viewA.trial_balance_id,
    tab: "trial_balance",
    layer: "unadjusted",
    ov: `signoff:trial_balance:${viewA.trial_balance_id}:L2`,
  },
  g: {
    engagementId: HARLOW_ENGAGEMENT,
    tbId: harlow.trial_balance_id,
    tab: "trial_balance",
    layer: "unadjusted",
    planned: { entities: HARLOW_ENTITIES, entity: "Manufacturing" },
  },
  h: {
    engagementId: GRANITE_ENGAGEMENT,
    tbId: GRANITE_TB,
    tab: "trial_balance",
    layer: "final",
    planned: { handOffToTax: GRANITE_HAND_OFF },
  },
  empty: {
    engagementId: GRANITE_ENGAGEMENT,
    tbId: null,
    tab: "trial_balance",
    layer: "unadjusted",
  },
  newer: {
    engagementId: GRANITE_ENGAGEMENT,
    tbId: GRANITE_TB,
    tab: "trial_balance",
    layer: "unadjusted",
  },
  loading: {
    engagementId: GRANITE_ENGAGEMENT,
    tbId: null,
    tab: "trial_balance",
    layer: "unadjusted",
  },
  error: {
    engagementId: GRANITE_ENGAGEMENT,
    tbId: null,
    tab: "trial_balance",
    layer: "unadjusted",
  },
  not_allowed: {
    engagementId: GRANITE_ENGAGEMENT,
    tbId: GRANITE_TB,
    tab: "trial_balance",
    layer: "unadjusted",
  },
};
