// POR-08 · Approvals (R-02-T13; R-02 §3.1): Dana Kowalski on Sep 25, before her entry decisions
// (a) and after them with the uncorrected acknowledgement waiting (e), from seed/portal-r02.ts.
import { json, type Scenario } from "../../app-core/fixture-mode";
import {
  AJE1_DETAIL,
  APPROVALS_AFTER,
  APPROVALS_BEFORE,
  ID,
  PERSONAS,
  R02_CLOCK,
} from "../seed/portal-r02";

export type Por08State = "a" | "e";

const detail = `GET /v1/portal/approvals/proposed_entry/${ID.aje1}`;

export const scenarios: Readonly<Record<Por08State, Scenario>> = {
  a: {
    state: "a",
    persona: PERSONAS.dana,
    clock: R02_CLOCK,
    handlers: {
      "GET /v1/portal/approvals": () => json(APPROVALS_BEFORE),
      [detail]: () => json(AJE1_DETAIL),
    },
  },
  e: {
    state: "e",
    persona: PERSONAS.dana,
    clock: R02_CLOCK,
    handlers: {
      "GET /v1/portal/approvals": () => json(APPROVALS_AFTER),
      [detail]: () => json({ ...AJE1_DETAIL, ...APPROVALS_AFTER.items[0] }),
    },
  },
};
