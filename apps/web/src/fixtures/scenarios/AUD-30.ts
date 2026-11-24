// AUD-30 fixture scenarios (Q-05-T24, TASK-8934; docs/screens/AUD-30.md): Margaret Okonkwo on the
// archived Northwind audit, Mon Jan 25, 2027, 9:24 AM CT. The cases, additions and analysis come
// from the Python slice (`seed/aud30.ts`); the cockpit is Northwind's, archived, with the
// server's Post-issuance overview row. a: PI-01 under evaluation; b: decided "No action" (the
// addition logged); c: decided "Revise and reissue"; d: PI-02 selected; e: the Archive additions
// tab; f: the New case sheet. Decide, Reopen for reissue and New case write through handlers.
import type { AuditCockpitOut, CapabilitiesOut, PostIssuanceCaseOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  AUD30_CLOCK,
  type Aud30Decided,
  additions,
  analysis,
  cases,
  decide,
  opened,
} from "../seed/aud30";
import { capabilitiesFor } from "../seed/shell";
import { NORTHWIND_AUDIT } from "./AUD-06";

export { NORTHWIND_AUDIT as AUD30_AUDIT_ID };
const seed = getSeed();
const E0 = seedScenario();
const COCKPIT = "GET /v1/audits/{work_item_id}/cockpit";
const C = "/v1/audits/{work_item_id}/post-issuance/cases";

/** The sub-line the server's Post-issuance row computes (`providers.post_issuance_row`). */
export function railLine(all: readonly PostIssuanceCaseOut[]): string {
  const waiting = all.filter((c) => c.status === "under_evaluation").length;
  const reissue = all.some((c) => c.status === "reissue_in_progress");
  const n = `${String(all.length)} case${all.length === 1 ? "" : "s"}`;
  return `${n} · ${reissue ? "reissue in progress" : waiting > 0 ? `${String(waiting)} awaiting decision` : "all concluded"}`;
}

function archived(base: FixtureHandler, all: () => PostIssuanceCaseOut[]): FixtureHandler {
  return async (request) => {
    const response = await base(request);
    if (!response.ok) return response;
    const cockpit = (await response.json()) as AuditCockpitOut;
    const bands = (cockpit.bands ?? []).map((band) =>
      band.key !== "overview"
        ? band
        : {
            ...band,
            rows: [
              ...(band.rows ?? []).filter((r) => r.key !== "post_issuance"),
              {
                key: "post_issuance",
                title: "Post-issuance",
                route: "AUD-30",
                link: "live" as const,
                work_item_ref: cockpit.work_item_id,
                grammar: "link" as const,
                sub_line: railLine(all()),
                allowed_actions: [],
              },
            ],
          },
    );
    return json({
      ...cockpit,
      overview: { ...cockpit.overview, phase: "archived" as const },
      read_only_reason: "archived" as const,
      bands,
    });
  };
}

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "margaret-okonkwo");
  return {
    ...base,
    flags: { ...base.flags, "audits.cockpit": true, "audit.post_issuance": true },
  };
}

function at(state: string, decided: Aud30Decided): Scenario {
  return {
    state,
    persona: "margaret-okonkwo",
    clock: AUD30_CLOCK,
    get handlers(): Record<string, FixtureHandler> {
      let all = cases(decided);
      let added: string | null =
        decided === "no_action" ? "Corrected certification and evaluation (PI-01)" : null;
      const audits = auditHandlers(seed, "run");
      const cockpit = audits[COCKPIT];
      return {
        ...E0.handlers,
        ...audits,
        ...(cockpit === undefined ? {} : { [COCKPIT]: archived(cockpit, () => all) }),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
        [`GET ${C}`]: () => json({ items: all, archive_locked_at: "2026-12-03T22:00:00Z" }),
        [`GET ${C}/{case_id}`]: ({ params }) => {
          const found = all.find((c) => c.case_id === params.case_id);
          return found === undefined ? json({ code: "not_found" }, 404) : json(found);
        },
        [`GET ${C}/{case_id}/analysis`]: ({ params }) => {
          const kept = analysis();
          return params.case_id === kept.case_id ? json(kept) : json({ code: "not_found" }, 404);
        },
        [`POST ${C}`]: ({ body }) => {
          const made = opened(body as Parameters<typeof opened>[0]);
          all = [...all, made];
          return json(made, 201);
        },
        [`POST ${C}/{case_id}/decision`]: ({ params, body: raw }) => {
          const body = raw as Parameters<typeof decide>[2];
          const done = decide(all, params.case_id ?? "", body);
          if (done === undefined) return json({ code: "not_found" }, 404);
          all = all.map((c) => (c.case_id === done.case_id ? done : c));
          if (done.source_evidence_version_id != null && done.ref === "PI-01") {
            added = body.addition_description ?? `${done.description} (${done.ref})`;
          }
          return json(done);
        },
        [`POST ${C}/{case_id}/reopen-for-reissue`]: ({ params }) =>
          json({
            case_id: params.case_id,
            report_release_id: "00000000-0000-4000-8000-0000000a3001",
            href: "/audits/x/report",
          }),
        "GET /v1/audits/{work_item_id}/archive/additions": () => json({ items: additions(added) }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", null),
  b: at("b", "no_action"),
  c: at("c", "revise_and_reissue"),
  d: at("d", null),
  e: at("e", null),
  f: at("f", null),
});
export type Aud30State = keyof typeof scenarios;
