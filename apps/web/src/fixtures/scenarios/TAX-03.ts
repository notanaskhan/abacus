// TAX-03 · Return › Intake a–f (T-02-T19): T-02-T08's personas and clocks (tax-returns.ts), each
// answering the intake read for its artboard (seed/tax-intake.ts), BND-02's live poll, the SHL-08
// viewer for a2 and the person's writes: N-01's triage apply (File to request, Not this…, Ignore),
// C5's Approve Document, T-02-T17's duplicate resolution and the binder's unpublish. Each write
// answers as the live route does; the screen refetches the read.
import type { TaxReturnRecordOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { taxReturnHandlers } from "../handlers/tax-returns";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { TAX_RETURNS } from "../seed/tax";
import {
  DUPLICATE_VERSION,
  FELD_BINDER_ID,
  type IntakeVariant,
  REQUEST,
  intakeFor,
  liveFor,
} from "../seed/tax-intake";
import { DOCUMENTS, W2_CLAIRE } from "../seed/trust";

const E0 = seedScenario();

function returnOf(client: string): string {
  const row = TAX_RETURNS.find((r) => r.client === client && !r.label.endsWith(":2"));
  if (row === undefined) throw new Error(`no TY2025 return for ${client}`);
  return row.id;
}

export type Tax03State = "a" | "a2" | "b" | "c" | "d" | "e" | "f";

/** The return each artboard opens: the Feld 2025 Form 1040, and Meera Shah's in f. */
export const OPENS: Readonly<Record<Tax03State, string>> = {
  a: returnOf("Jonah & Claire Feld"),
  a2: returnOf("Jonah & Claire Feld"),
  b: returnOf("Jonah & Claire Feld"),
  c: returnOf("Jonah & Claire Feld"),
  d: returnOf("Jonah & Claire Feld"),
  e: returnOf("Jonah & Claire Feld"),
  f: returnOf("Meera Shah"),
};

/** a2 opens the W-2 request in the dock (its seeded SHL-08 document). */
export const OPEN_DOCUMENT: Partial<Record<Tax03State, string>> = { a2: REQUEST.w2 };
export { DUPLICATE_VERSION, FELD_BINDER_ID, REQUEST, W2_CLAIRE };

function frame(
  state: Tax03State,
  clock: string,
  variant: IntakeVariant,
  extra: Record<string, FixtureHandler> = {},
): Scenario {
  const returns = taxReturnHandlers("a");
  const record = returns["GET /v1/tax-returns/{return_id}"];
  return {
    state,
    persona: "kevin-osei",
    clock,
    handlers: {
      ...E0.handlers,
      ...returns,
      ...trustHandlers({ citations: [], documents: DOCUMENTS }),
      "GET /v1/tax-returns/{return_id}": async (request) => {
        if (record === undefined) return json({ detail: "not_found" }, 404);
        const answer = await record(request);
        if (variant !== "c" && variant !== "d") return answer;
        // c and d: both open requests satisfied, so the tab reads "Intake" with no count.
        const body = (await answer.json()) as TaxReturnRecordOut;
        return json({
          ...body,
          tabs: body.tabs.map((t) => (t.tab === "intake" ? { ...t, count: null } : t)),
        });
      },
      "GET /v1/tax-returns/{return_id}/intake": ({ params }) =>
        json(intakeFor(variant, params.return_id ?? "")),
      "GET /v1/binders/{binder_id}/live": () => json({ items: liveFor(variant), as_of: clock }),
      "POST /v1/inbox/messages/{message_id}/triage/apply": ({ body }) => {
        const decisions = (body as { decisions?: { decision: string }[] } | null)?.decisions ?? [];
        return json({
          filed: decisions.filter((d) => d.decision === "file").length,
          ignored: decisions.filter((d) => d.decision === "ignore").length,
          held: decisions.filter((d) => d.decision === "hold").length,
          undo_grant_id: null,
          notified_user_ids: [],
        });
      },
      "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/accept": ({
        params,
      }) =>
        json({
          id: `decision:${params.version_id ?? ""}`,
          evidence_version_id: params.version_id,
          decision: "accept",
        }),
      "POST /v1/engagements/{engagement_id}/request-items/{item_id}/evidence-versions/{version_id}/duplicate-resolution":
        ({ params, body }) => {
          const decision = (body as { decision?: string } | null)?.decision ?? "discard_duplicate";
          return json({
            decision,
            evidence_version_id: params.version_id,
            kept_version_id: decision === "keep_newer" ? params.version_id : W2_CLAIRE,
          });
        },
      "POST /v1/binders/{binder_id}/unpublish": ({ params }) =>
        json({ binder_id: params.binder_id, status: "draft" }),
      ...extra,
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", "2026-09-14T09:24:00-05:00", "a"),
  a2: frame("a2", "2026-09-14T09:24:00-05:00", "a"),
  b: frame("b", "2026-09-14T09:26:00-05:00", "b"),
  c: frame("c", "2026-09-15T09:02:00-05:00", "c"),
  d: frame("d", "2026-09-15T10:30:00-05:00", "d"),
  e: frame("e", "2026-09-14T09:24:00-05:00", "e"),
  f: frame("f", "2026-09-14T09:24:00-05:00", "f"),
});
