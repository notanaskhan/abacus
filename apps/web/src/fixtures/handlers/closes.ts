// C-01-T12 and C-01-T13: the closes screens in fixture mode, typed against the closes stubs
// (C-01-T04, T05) and drawn from the Copperleaf figure book (`seed/close-book.ts`). The record
// answers Copperleaf August for every close id; the portfolio filters by the CLS-01 query
// (`status`, `past_due`, `attest`, `q`); the reads a later row owns stay 501 until it lands.
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  closesPortfolio,
  copperleafFluxAt,
  copperleafFluxYoy,
  copperleafIssues,
  closeTemplates,
  copperleafPlan,
  copperleafPlanHistory,
  copperleafPortalQuestions,
  copperleafReconciliation4410,
  copperleafRun2,
  copperleafRuns,
  runningCloses,
} from "../seed/close-book";
import {
  SQUARE_VERSION,
  augustQuestionnaire,
  copperleafRequestTree,
  squareSummary,
} from "../seed/close-intake";
import { copperleafAugust } from "../seed/closes";

const notYet = () => json({ detail: "not_implemented" }, 501);

export function closeHandlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/closes": ({ query }) => {
      const status = query.get("status");
      const attest = query.get("attest");
      const q = query.get("q")?.toLowerCase();
      return json(
        closesPortfolio(
          (r) =>
            (status == null ||
              (status === "past_due" ? r.days_past_due != null : r.status === status)) &&
            (attest == null || r.attest === (attest === "true")) &&
            (q == null || r.client_name.toLowerCase().includes(q)),
        ),
      );
    },
    "GET /v1/closes/running": () => json(runningCloses()),
    "GET /v1/closes/{close_id}": () => json(copperleafAugust()),
    "GET /v1/closes/{close_id}/runs": () => json(copperleafRuns()),
    "GET /v1/closes/{close_id}/runs/{run_no}": ({ params }) =>
      params.run_no === "2" ? json(copperleafRun2()) : notYet(),
    "GET /v1/closes/{close_id}/reconciliations/{account_ref}": ({ params }) =>
      params.account_ref === "35" ? json(copperleafReconciliation4410()) : notYet(),
    "GET /v1/closes/{close_id}/issues": () => json(copperleafIssues()),
    "GET /v1/closes/{close_id}/flux": ({ query }) => {
      const basis = query.get("basis") ?? "mom";
      if (basis === "mom") return json(copperleafFluxAt("a"));
      return basis === "yoy" ? json(copperleafFluxYoy()) : json({ detail: "not_found" }, 404);
    },
    "GET /v1/clients/{client_id}/close-plan": () => json(copperleafPlan()),
    "GET /v1/clients/{client_id}/close-plan/versions": () => json(copperleafPlanHistory()),
    "GET /v1/close-templates": () => json(closeTemplates()),
    "GET /v1/portal/closes/{close_id}/questions": () => json(copperleafPortalQuestions()),
    "GET /v1/closes/{close_id}/requests": () => json(copperleafRequestTree()),
    "GET /v1/closes/{close_id}/questionnaire": () => json(augustQuestionnaire()),
    "GET /v1/evidence-versions/{evidence_version_id}/close-summary": ({ params }) =>
      params.evidence_version_id === SQUARE_VERSION ? json(squareSummary()) : notYet(),
    "GET /v1/closes/{close_id}/accounts": notYet,
  };
}
