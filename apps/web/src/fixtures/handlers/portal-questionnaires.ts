// POR-05's portal questionnaire routes on fixtures (T-02-T24; T-02-T22's shapes): the list and
// detail by artboard, autosave with If-Match on the answer's version (a stale version answers 409
// `stale_version` so the screen reloads the answer instead of overwriting it), attachments,
// Mark as Done and Submit. Answers live in memory for the page's life.
import type { QuestionnaireOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { questionnairesOf } from "../seed/portal-questionnaires";

const NOT_FOUND = { detail: "not found" };

/** Another device's save: the next write at the version the screen holds is stale (tests). */
export const STALE_FROM_ELSEWHERE = new Map<
  string,
  QuestionnaireOut["questions"][number]["answer"]
>();

export function portalQuestionnaireHandlers(state: string): Record<string, FixtureHandler> {
  const held = new Map<string, QuestionnaireOut>(questionnairesOf(state).map((x) => [x.id, x]));
  const find = (id: string | undefined): QuestionnaireOut | undefined =>
    id === undefined ? undefined : held.get(id);
  return {
    "GET /v1/portal/questionnaires": () => json([...held.values()]),
    "GET /v1/portal/questionnaires/{questionnaire_id}": ({ params }) => {
      const found = find(params.questionnaire_id);
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    "PUT /v1/portal/questionnaires/{questionnaire_id}/answers/{question_id}": ({
      params,
      body,
      headers,
    }) => {
      const found = find(params.questionnaire_id);
      const question = found?.questions.find((x) => x.id === params.question_id);
      if (found === undefined || question === undefined) return json(NOT_FOUND, 404);
      const elsewhere = STALE_FROM_ELSEWHERE.get(question.id);
      if (elsewhere !== undefined) {
        STALE_FROM_ELSEWHERE.delete(question.id);
        question.answer = elsewhere;
        question.answer_version = (question.answer_version ?? 0) + 1;
      }
      const seen = Number(headers?.get("If-Match") ?? "0");
      if (seen !== (question.answer_version ?? 0)) {
        return json({ detail: "stale_version" }, 409);
      }
      question.answer = (body as { value: QuestionnaireOut["questions"][number]["answer"] }).value;
      question.answer_version = seen + 1;
      found.answered = found.questions.filter(
        (x) => x.answer !== null && x.section !== "Questions from your team",
      ).length;
      return json({ saved_at: "2026-09-14T09:24:00-05:00", version: seen + 1 });
    },
    "POST /v1/portal/questionnaires/{questionnaire_id}/questions/{question_id}/attachments": () =>
      json({ saved_at: "2026-09-14T09:24:00-05:00", version: 1 }, 201),
    "POST /v1/portal/questionnaires/{questionnaire_id}:mark-done": ({ params }) => {
      const found = find(params.questionnaire_id);
      if (found === undefined) return json(NOT_FOUND, 404);
      found.status = "complete";
      return json(found);
    },
    "POST /v1/portal/questionnaires/{questionnaire_id}:submit": ({ params }) => {
      const found = find(params.questionnaire_id);
      if (found === undefined) return json(NOT_FOUND, 404);
      found.status = "submitted";
      return json(found);
    },
  };
}
