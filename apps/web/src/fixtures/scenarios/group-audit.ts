// A-09's fixture scenarios, one per lettered artboard (A-09-T07; A-09 §5.4; docs/screens/AUD-32
// to AUD-35 and POR-23). Brightwater Hale epoch E1; persona and clock per artboard. Every scenario
// answers the A-09 stub routes with a typed variant of `seed/group-audit.ts`, whose totals are
// computed from the entity columns and eliminations; a variant changes facts (a status, an
// attachment's state, one edited line), never a total by hand.
//
// The screens themselves land with A-09-T24 to T26 and T35 to T37; these scenarios are what they
// mount, and `fixtures/contracts/group-audit-scenarios.test.ts` foots every one.

import type {
  ComponentRoomOut,
  ConsolidatedTbOut,
  ConsolidationOut,
  EliminationOut,
  EliminationsOut,
  GroupScopingOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import {
  COMPONENT_ROOM_INVITED,
  CONSOLIDATED_TB_L1,
  CONSOLIDATED_TB_L2,
  CONSOLIDATION_REVIEW,
  ELIMINATIONS,
  GROUP_SCOPING_DECIDED,
} from "../seed/group-audit";

const E0 = seedScenario();
const SEP14 = (time: string) => `2026-09-14T${time}:00-05:00`;
const W = "/v1/audits/{work_item_id}";
const C = `${W}/consolidations/{consolidation_id}`;

function scenario(
  state: string,
  persona: string,
  clock: string,
  handlers: Record<string, FixtureHandler>,
): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return { ...E0.handlers, ...handlers };
    },
  };
}

// --- AUD-32 consolidation setup --------------------------------------------------------------

/** a: 9 of 10 attached; Real Estate's prior TB is missing. */
export function aud32Missing(): ConsolidationOut {
  return {
    ...CONSOLIDATION_REVIEW,
    entities: CONSOLIDATION_REVIEW.entities.map((e) =>
      e.name.endsWith("Real Estate, LLC")
        ? {
            ...e,
            trial_balances: [
              ...e.trial_balances,
              {
                id: `${e.id}-prior`,
                label: "prior",
                period_kind: "prior",
                period_start: "2025-01-01",
                period_end: "2025-12-31",
                state: "missing",
                file_name: null,
                total_debits: null,
                not_needed_reason: null,
              },
            ],
          }
        : e,
    ),
    all_balanced: false,
    missing: ["Real Estate · Prior"],
    allowed_actions: ["consolidation.edit"],
  };
}

function aud32NeedsReauth(): ConsolidationOut {
  return {
    ...CONSOLIDATION_REVIEW,
    entities: CONSOLIDATION_REVIEW.entities.map((e) =>
      e.component_auditor_name === null
        ? e
        : {
            ...e,
            trial_balances: e.trial_balances.map((t) => ({
              ...t,
              state: "needs_reauth",
              total_debits: null,
            })),
          },
    ),
    all_balanced: false,
    missing: ["Distribution · Interim"],
  };
}

const AUD32_FINALIZED: ConsolidationOut = {
  ...CONSOLIDATION_REVIEW,
  status: "finalized",
  finalized_by_name: "Omar Haddad",
  finalized_at: SEP14("10:48"),
  allowed_actions: ["consolidation.lock"],
};

function aud32(state: string, clock: string, body: ConsolidationOut): Scenario {
  return scenario(state, "omar-haddad", SEP14(clock), {
    [`GET ${C}`]: () => json(body),
    [`POST ${C}/finalize`]: () =>
      body.missing.length > 0
        ? json({ detail: "trial_balance_missing" }, 409)
        : json(AUD32_FINALIZED),
  });
}

export const aud32Scenarios = defineScenarios({
  a: aud32("a", "10:44", aud32Missing()),
  b: aud32("b", "10:31", { ...CONSOLIDATION_REVIEW, entities: [], all_balanced: false }),
  c: aud32("c", "10:36", {
    ...CONSOLIDATION_REVIEW,
    entities: CONSOLIDATION_REVIEW.entities.map((e) => ({ ...e, trial_balances: [] })),
  }),
  d: aud32("d", "10:47", CONSOLIDATION_REVIEW),
  e: aud32("e", "10:48", AUD32_FINALIZED),
  f: aud32("f", "10:44", aud32NeedsReauth()),
});

// --- AUD-33 consolidated TB and eliminations -------------------------------------------------

function proposed(e: EliminationOut): EliminationOut {
  return { ...e, status: "proposed", approved_by_name: null, posted_at: null };
}

/** c: E3's credit edited to 250,000 (off 10,000); E4 approved, not posted. */
export function aud33Unbalanced(): EliminationsOut {
  const items = ELIMINATIONS.items.map((e) => {
    if (e.display_code === "E3") {
      return {
        ...proposed(e),
        lines: e.lines.map((l) => (l.credit === "0.00" ? l : { ...l, credit: "250000.00" })),
        total_credit: "250000.00",
        off_by: "-10000.00",
      };
    }
    if (e.display_code === "E4") return { ...e, status: "approved" as const, posted_at: null };
    return e;
  });
  return { ...ELIMINATIONS, items };
}

function tbWith(
  tb: ConsolidatedTbOut,
  tallies: Partial<ConsolidatedTbOut["tallies"]>,
): ConsolidatedTbOut {
  return { ...tb, tallies: { ...tb.tallies, ...tallies } };
}

function aud33(
  state: string,
  clock: string,
  tb: ConsolidatedTbOut,
  eliminations: EliminationsOut,
  locked = false,
): Scenario {
  return scenario(state, "omar-haddad", SEP14(clock), {
    [`GET ${C}/tb`]: ({ query }) => json(query.get("level") === "2" ? CONSOLIDATED_TB_L2 : tb),
    "GET /v1/consolidations/{consolidation_id}/eliminations": () => json(eliminations),
    [`GET ${C}`]: () =>
      json({
        ...AUD32_FINALIZED,
        lock_state: locked ? "locked" : "open",
      }),
    "POST /v1/proposed-entries/{entry_id}/elimination/approve": ({ params }) => {
      const found = eliminations.items.find((e) => e.id === params.entry_id);
      return found !== undefined && found.off_by !== "0.00"
        ? json({ detail: "unbalanced_entry" }, 409)
        : json(found ?? {}, found === undefined ? 404 : 200);
    },
  });
}

export const aud33Scenarios = defineScenarios({
  a: aud33("a", "14:05", CONSOLIDATED_TB_L1, ELIMINATIONS),
  b: aud33(
    "b",
    "13:33",
    tbWith(CONSOLIDATED_TB_L1, {
      balanced: "pending",
      intercompany: "pending",
      eliminations_posted: 0,
    }),
    { ...ELIMINATIONS, items: ELIMINATIONS.items.map(proposed) },
  ),
  c: aud33(
    "c",
    "14:05",
    tbWith(CONSOLIDATED_TB_L1, {
      balanced: "off",
      off_by: "10000.00",
      intercompany: "off",
      intercompany_off_by: "2400000.00",
      total_assets: "53160000.00",
      eliminations_posted: 4,
    }),
    aud33Unbalanced(),
  ),
  d: aud33("d", "14:05", CONSOLIDATED_TB_L2, ELIMINATIONS),
  e: aud33("e", "14:05", CONSOLIDATED_TB_L1, ELIMINATIONS),
  f: aud33("f", "14:20", CONSOLIDATED_TB_L1, ELIMINATIONS, true),
  g: aud33("g", "14:05", { ...CONSOLIDATED_TB_L1, view: "entity:manufacturing" }, ELIMINATIONS),
});

// --- AUD-34 group scoping --------------------------------------------------------------------

const AUD34_BLOCKED: GroupScopingOut = {
  ...GROUP_SCOPING_DECIDED,
  decided: false,
  group_materiality: null,
  performance_materiality: null,
  clearly_trivial: null,
  decided_by_name: null,
  decided_at: null,
  components: GROUP_SCOPING_DECIDED.components.map((c) => ({
    ...c,
    component_pm: null,
    pm_pct_of_group: null,
  })),
  allowed_actions: ["decision.decide", "component.edit"],
};

function aud34(
  state: string,
  persona: string,
  clock: string,
  body: GroupScopingOut,
  off = false,
): Scenario {
  return scenario(state, persona, SEP14(clock), {
    [`GET ${W}/group-scoping`]: () => (off ? json({ detail: "not_found" }, 404) : json(body)),
  });
}

export const aud34Scenarios = defineScenarios({
  a: aud34("a", "margaret-okonkwo", "15:38", AUD34_BLOCKED),
  b: aud34("b", "omar-haddad", "15:10", { ...AUD34_BLOCKED, allowed_actions: ["component.edit"] }),
  c: aud34("c", "margaret-okonkwo", "15:40", GROUP_SCOPING_DECIDED),
  d: aud34("d", "omar-haddad", "14:55", AUD34_BLOCKED),
  e: aud34("e", "margaret-okonkwo", "15:38", GROUP_SCOPING_DECIDED),
  f: aud34("f", "margaret-okonkwo", "15:38", AUD34_BLOCKED, true),
});

// --- AUD-35 component auditors ---------------------------------------------------------------

type InstructionsStatus = "draft" | "sent" | "acknowledged";

function aud35(
  state: string,
  persona: string,
  clock: string,
  status: InstructionsStatus,
  opts: { late?: boolean; received?: boolean; makeReference?: boolean; off?: boolean } = {},
): Scenario {
  return scenario(state, persona, clock, {
    [`GET ${W}/component-auditors`]: () =>
      opts.off === true
        ? json({ detail: "not_found" }, 404)
        : json({
            items: [
              {
                id: "ca-pruett-lang",
                organisation_name: "Pruett & Lang LLP",
                city: "Denver",
                component_id: GROUP_SCOPING_DECIDED.components[1]?.id ?? "component",
                contact_name: "Renee Pruett",
                questionnaire_received_on: "2026-09-10",
                competence_evaluated_at: "2026-09-11T10:00:00-05:00",
                independence_confirmed_at: "2026-09-11T10:00:00-05:00",
                peer_review_obtained_on: "2026-09-10",
                make_reference: opts.makeReference === true,
                instructions_status: status,
              },
            ],
          }),
    "GET /v1/component-auditors/{auditor_id}/deliverables": () =>
      json({
        items: COMPONENT_ROOM_INVITED.deliverables.map((d, i) => ({
          id: d.id,
          title: d.title,
          due_on: d.due_on,
          status:
            i === 0 && opts.received === true
              ? "received"
              : i === 0 && opts.late === true
                ? "late"
                : "expected",
          days_late: i === 0 && opts.late === true ? 1 : null,
          received_at: i === 0 && opts.received === true ? "2026-12-02T09:00:00-06:00" : null,
          reviewed_by_name: null,
          return_reason: null,
        })),
      }),
  });
}

export const aud35Scenarios = defineScenarios({
  a: aud35("a", "omar-haddad", SEP14("16:30"), "draft"),
  b: aud35("b", "omar-haddad", "2026-09-21T14:20:00-05:00", "sent"),
  c: aud35("c", "omar-haddad", "2026-09-23T11:20:00-05:00", "acknowledged"),
  d: aud35("d", "margaret-okonkwo", "2026-12-01T08:30:00-06:00", "acknowledged", { late: true }),
  e: aud35("e", "omar-haddad", "2026-12-02T10:00:00-06:00", "acknowledged", { received: true }),
  f: aud35("f", "omar-haddad", SEP14("16:30"), "draft", { makeReference: true }),
  g: aud35("g", "omar-haddad", SEP14("16:30"), "draft", { off: true }),
});

// --- POR-23 the component auditor room -------------------------------------------------------

function room(
  patch: Partial<ComponentRoomOut>,
  deliverableWords: ComponentRoomOut["deliverables"][number]["word"][] = [],
): ComponentRoomOut {
  return {
    ...COMPONENT_ROOM_INVITED,
    ...patch,
    deliverables: COMPONENT_ROOM_INVITED.deliverables.map((d, i) => ({
      ...d,
      word: deliverableWords[i] ?? d.word,
    })),
  };
}

function por23(state: string, clock: string, body: ComponentRoomOut | null): Scenario {
  return scenario(state, "renee-pruett", clock, {
    "GET /v1/portal/component-rooms/{room_id}": () =>
      body === null ? json({ detail: "not_found" }, 404) : json(body),
  });
}

export const por23Scenarios = defineScenarios({
  a: por23("a", "2026-09-23T09:40:00-05:00", COMPONENT_ROOM_INVITED),
  b: por23("b", "2026-09-23T11:20:00-05:00", room({ acknowledged_on: "2026-09-23" })),
  c: por23(
    "c",
    "2026-12-01T09:05:00-06:00",
    room({ acknowledged_on: "2026-09-23", uploaded: 1 }, ["overdue"]),
  ),
  d: por23(
    "d",
    "2026-12-02T10:00:00-06:00",
    room({ acknowledged_on: "2026-09-23", uploaded: 2 }, ["you_uploaded", "you_uploaded"]),
  ),
  e: por23(
    "e",
    "2026-09-23T09:40:00-05:00",
    room({ acknowledged_on: "2026-09-23", uploaded: 1 }, ["returned"]),
  ),
  f: por23("f", "2026-09-23T09:40:00-05:00", null),
});
