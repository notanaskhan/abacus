// POR-11 fixture scenarios (C-01-T41, DEC-5638; handoff POR-11): Copperleaf's August 2026 close
// as Ben Ashby sees it, Mon Sep 14, 2026. The questions are the close book's (`seed/close-book`);
// an answer comes back answered with its receipt time, the way the sealed answer route returns it.
// The request cards are POR-03's on the close's binder and join with the Copperleaf close binder
// seed (C-01-T44's CAS slice); until then those states show the questions card only.
import type { PortalAnswerIn, PortalQuestionOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { copperleafPortalQuestions } from "../seed/close-book";

const PERSONA = "ben-ashby";
const ANSWERED_AT = "2026-09-14T13:12:00-05:00";

function questions(answered: readonly string[]): PortalQuestionOut[] {
  return copperleafPortalQuestions().items.map((q) =>
    answered.some((key) => q.client_wording.includes(key))
      ? { ...q, status: "answered", answered_at: ANSWERED_AT }
      : q,
  );
}

function at(state: string, clock: string, answered: readonly string[] = []): Scenario {
  return {
    state,
    persona: PERSONA,
    clock,
    handlers: {
      "GET /v1/portal/closes/{close_id}/questions": () => json({ items: questions(answered) }),
      "POST /v1/portal/questions/{question_id}/answer": ({ params, body }) => {
        const q = questions(answered).find((x) => x.question_id === params.question_id);
        const answer = body as PortalAnswerIn;
        if (q === undefined || (answer.choice == null && !answer.note)) {
          return json({ code: "not_found" }, 404);
        }
        return json({ ...q, status: "answered", answered_at: ANSWERED_AT });
      },
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-09-14T09:24:00-05:00"),
  b: at("b", "2026-09-14T09:24:00-05:00"),
  c: at("c", "2026-09-14T13:15:00-05:00", ["Sound Electric"]),
});

export type Por11State = keyof typeof scenarios;
