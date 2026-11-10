// POR-15 · Governance room a–f (R-02-T21; docs/screens/POR-15.md): Victoria Lam's room on the
// portal handlers, answering the governance reads from seed/portal-por15.ts. NOT_ALLOWED is Dana
// Kowalski, whose management grant reaches no room (every room route 404s, DEC-93).
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { portalHandlers } from "../handlers/portal";
import { seedScenario } from "../scenario";
import {
  POR15_ID,
  type Por15State,
  communications,
  inquiries,
  letter,
  reports,
  rooms,
} from "../seed/portal-por15";

const E0 = seedScenario();
const G = "/v1/portal/governance";
const NOT_FOUND = { detail: "not found" };

function pdf(): Response {
  return new Response(new Uint8Array([37, 80, 68, 70]).buffer, {
    status: 200,
    headers: { "Content-Type": "application/pdf" },
  });
}

function handlers(state: Por15State | "n", clock: string): Record<string, FixtureHandler> {
  const base = { ...E0.handlers, ...portalHandlers({ clock }) };
  if (state === "n") {
    return {
      ...base,
      [`GET ${G}/rooms`]: () => json({ items: [] }),
      [`GET ${G}/rooms/{room_id}/communications`]: () => json(NOT_FOUND, 404),
      [`GET ${G}/communications/{communication_id}`]: () => json(NOT_FOUND, 404),
    };
  }
  const room = (r: { params: Record<string, string> }): boolean =>
    r.params.room_id === POR15_ID.room;
  return {
    ...base,
    [`GET ${G}/rooms`]: () => json(rooms(state)),
    [`GET ${G}/rooms/{room_id}/communications`]: (r) =>
      room(r) ? json(communications(state)) : json(NOT_FOUND, 404),
    [`GET ${G}/rooms/{room_id}/inquiries`]: (r) =>
      room(r) ? json(inquiries(state)) : json(NOT_FOUND, 404),
    [`GET ${G}/rooms/{room_id}/reports`]: (r) =>
      room(r) ? json({ items: reports(state) }) : json(NOT_FOUND, 404),
    [`GET ${G}/communications/{communication_id}`]: (r) => {
      const found = letter(state, r.params.communication_id ?? "");
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    [`GET ${G}/communications/{communication_id}/pdf`]: () => pdf(),
    "GET /v1/portal/deliverables/{deliverable_id}/versions/{version_no}/download": () => pdf(),
    [`POST ${G}/communications/{communication_id}/acknowledge`]: (r) =>
      json({
        communication_id: r.params.communication_id,
        status: "acknowledged",
        acknowledged_on: "2026-09-21",
      }),
    [`GET ${G}/communications/{communication_id}/questions`]: () => json({ items: [] }),
    [`POST ${G}/communications/{communication_id}/questions`]: (r) =>
      json(
        {
          id: "private-question-1",
          author: "Victoria Lam",
          body: (r.body as { body?: string } | undefined)?.body ?? "",
          created_at: "2026-09-21T13:31:00Z",
        },
        201,
      ),
    "GET /v1/portal/questionnaires/{questionnaire_id}": () =>
      json({
        id: POR15_ID.inquiries,
        title: "Questions from your auditor",
        kind: "inquiry",
        status: "sent",
        due_on: null,
        addressed_to_contact_id: null,
        answered: 0,
        total: 2,
        questions: inquiries(state).items.map((i) => ({
          id: i.question_id,
          client_wording: i.prompt,
          type: "long_text",
          section: "Fraud inquiries",
          answer: null,
          answer_version: 0,
          help_text: null,
          sent_at: "2026-09-18T14:00:00Z",
          prior_year_value: null,
          conditional_on_question_id: null,
          linked_request_item_id: null,
        })),
      }),
    "PUT /v1/portal/questionnaires/{questionnaire_id}/answers/{question_id}": () =>
      json({ saved_at: "2026-09-21T13:35:00Z", version: 1 }),
    "POST /v1/portal/questionnaires/{questionnaire_id}:submit": () =>
      json({ id: POR15_ID.inquiries, status: "submitted" }),
  };
}

function at(state: Por15State, clock: string): Scenario {
  return { state, persona: "victoria-lam", clock, handlers: handlers(state, clock) };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-09-21T08:30:00-05:00"),
  b: at("b", "2026-09-21T08:31:00-05:00"),
  c: at("c", "2026-09-21T08:30:00-05:00"),
  d: at("d", "2026-11-24T10:00:00-06:00"),
  e: at("e", "2026-10-12T10:00:00-05:00"),
  f: at("f", "2026-09-16T10:00:00-05:00"),
});

/** Not allowed (not an artboard): Dana Kowalski's management grant opens no room. */
export const NOT_ALLOWED: Scenario = {
  state: "n",
  persona: "dana-kowalski",
  clock: "2026-09-21T08:30:00-05:00",
  handlers: handlers("n", "2026-09-21T08:30:00-05:00"),
};

/** What an artboard opens with: c on Questions for you, d on the control letter, e on Reports. */
export const OPENING: Readonly<
  Partial<
    Record<
      Por15State,
      { tab?: "communications" | "reports" | "questions"; communicationId?: string }
    >
  >
> = {
  c: { tab: "questions" },
  d: { communicationId: POR15_ID.control },
  e: { tab: "reports" },
};

export type { Por15State };
export const STATES = Object.keys(scenarios) as Por15State[];
