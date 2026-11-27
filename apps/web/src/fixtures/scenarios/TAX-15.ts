// TAX-15 fixture scenarios (T-08-T32, DEC-6038; docs/screens/TAX-15.md): Daniel Reyes's TY2025
// planning queue at Mon Sep 14, 9:24 AM CT. The nine rows, the strip, the Feld rationale and
// sources, and Ferris's envelope are the Python scenario's (`seed/scenario.tax15-portfolio.json`,
// `make fixtures`, never hand written): a Feld selected, b after Raise (the row Raised), c the
// Ridgeline project prefill, d Ferris consent-blocked, e Show dismissed, f the per-return view.
import type { TaxPracticeOpportunityOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { stableId } from "../seed/prng";
import exported from "../seed/scenario.tax15-portfolio.json";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const DANIEL = stableId("person:daniel-reyes");
export const opportunityId = (title: string): string => stableId(`opportunity:${title}`);
export const clientIdOf = (client: string): string => stableId(`client:${client}`);
export const FELD_ID = opportunityId(exported.rows[0]?.title ?? "");
export const FERRIS_ID = opportunityId(
  exported.rows.find((r) => r.status === "not_screened")?.title ?? "",
);
export const COST_SEG_ID = opportunityId(
  exported.rows.find((r) => r.title.startsWith("Cost segregation"))?.title ?? "",
);
export const FELD_CLIENT = clientIdOf("Jonah & Claire Feld");
type Moment = "e0" | "raised";

function opportunity(
  row: (typeof exported.rows)[number],
  moment: Moment,
): TaxPracticeOpportunityOut {
  const feld = row.client === "Jonah & Claire Feld";
  const status =
    moment === "raised" && feld ? "raised" : (row.status as TaxPracticeOpportunityOut["status"]);
  const ferris = row.status === "not_screened";
  return {
    opportunity_id: opportunityId(row.title),
    client_id: clientIdOf(row.client),
    client_name: row.client,
    work_item_id: stableId(`tax-return:${row.client}:2025`),
    rule_key: row.rule_key,
    category: row.category,
    title: row.title,
    status,
    est_savings: row.est_savings,
    rationale: feld ? exported.feld.rationale : null,
    rationale_source: feld ? "agent" : null,
    citations: feld
      ? exported.feld.sources.map((s, i) => ({
          citation_id: stableId(`citation:feld:planning:${String(i)}`),
          label: `${s.title} · ${s.loc}`,
          verified: true,
        }))
      : [],
    consent_envelope_id: ferris ? stableId(`envelope:${exported.ferris_envelope}`) : null,
    raised_at: status === "raised" ? "2026-09-14T09:30:00-05:00" : null,
    project_engagement_id: null,
    row_version: 1,
    allowed_actions:
      ferris || status !== "open"
        ? []
        : ["planning.raise", "planning.create_project", "planning.dismiss"],
    consent_basis: "301_7216_2h",
    owner_user_id: DANIEL,
    tax_year: exported.tax_year,
  };
}

export function queue(moment: Moment, client?: string): TaxPracticeOpportunityOut[] {
  return exported.rows
    .filter((r) => client === undefined || clientIdOf(r.client) === client)
    .map((r) => opportunity(r, moment));
}

function at(state: string, moment: Moment): Scenario {
  return {
    state,
    persona: "daniel-reyes",
    clock: "2026-09-14T09:24:00-05:00",
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), persona ?? "daniel-reyes");
          return json({ ...base, flags: { ...base.flags, "tax.planning": true } });
        },
        "GET /v1/planning-summary": () =>
          json({ tax_year: exported.tax_year, ...exported.summary }),
        "GET /v1/planning-opportunities": ({ query }: { query: URLSearchParams }) => {
          const items = queue(moment, query.get("client_id") ?? undefined);
          return json({ items, total: exported.summary.opportunities, next_cursor: null });
        },
        "POST /v1/planning-opportunities/{opportunity_id}:prepare-raise": () =>
          json({
            template_id: null,
            subject: exported.rows[0]?.title ?? "",
            body: exported.feld.talking_points.join("\n"),
            draft_from_agent: true,
            recipients: ["Claire Feld"],
            recipient_contact_ids: [stableId("contact:claire-feld")],
          }),
        "POST /v1/planning-opportunities/{opportunity_id}:raise": () => json(queue("raised")[0]),
        "POST /v1/planning-opportunities/{opportunity_id}:create-project": () =>
          json({
            client_id: clientIdOf("Ridgeline Property Partners, LP"),
            engagement_name: exported.ridgeline_project,
            owner_user_id: DANIEL,
            source_ref: `planning_opportunity:${COST_SEG_ID}`,
          }),
        "POST /v1/planning-opportunities/{opportunity_id}:dismiss": () =>
          json({ ...queue(moment)[0], status: "dismissed" }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "e0"), // Default (Feld selected)
  b: at("b", "raised"), // Raised
  c: at("c", "e0"), // Accepted → project (Ridgeline cost segregation)
  d: at("d", "e0"), // Consent-blocked (Ferris)
  e: at("e", "e0"), // Dismissed (Show dismissed)
  f: at("f", "e0"), // Per-return view (Feld)
});

export type Tax15State = keyof typeof scenarios;

/** How each artboard opens: the selected row, the client chip, Show dismissed. */
export const INITIAL: Record<
  Tax15State,
  { selected?: string; client?: string; dismissDialog?: boolean }
> = {
  a: { selected: FELD_ID },
  b: { selected: FELD_ID },
  c: { selected: COST_SEG_ID },
  d: { selected: FERRIS_ID },
  e: { selected: FELD_ID, dismissDialog: true },
  f: { selected: FELD_ID, client: FELD_CLIENT },
};
