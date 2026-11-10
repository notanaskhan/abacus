// POR-15 · Governance room (R-02-T13; R-02 §3.5): Victoria Lam in the Benefits Committee room (a),
// and Dana Kowalski, whose management grant reaches no room (n: every room route 404s, DEC-93).
import { json, type Scenario } from "../../app-core/fixture-mode";
import { ID, PERSONAS, PLANNING_LETTER, R02_CLOCK, ROOM_LETTERS, ROOMS } from "../seed/portal-r02";

export type Por15State = "a" | "n";

const NOT_FOUND = { detail: "not_found" };

export const scenarios: Readonly<Record<Por15State, Scenario>> = {
  a: {
    state: "a",
    persona: PERSONAS.victoria,
    clock: R02_CLOCK,
    handlers: {
      "GET /v1/portal/governance/rooms": () => json(ROOMS),
      [`GET /v1/portal/governance/rooms/${ID.room}/communications`]: () => json(ROOM_LETTERS),
      [`GET /v1/portal/governance/communications/${ID.planningLetter}`]: () =>
        json(PLANNING_LETTER),
    },
  },
  n: {
    state: "n",
    persona: PERSONAS.dana,
    clock: R02_CLOCK,
    handlers: {
      "GET /v1/portal/governance/rooms": () => json({ items: [] }),
      [`GET /v1/portal/governance/rooms/${ID.room}/communications`]: () => json(NOT_FOUND, 404),
      [`GET /v1/portal/governance/communications/${ID.planningLetter}`]: () =>
        json(NOT_FOUND, 404),
    },
  },
};
