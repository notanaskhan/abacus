// POR-09 · Deliverables a–f (R-02-T17; docs/screens/POR-09.md): the personas and clocks of the
// screen contract on the portal handlers, answering the deliverables reads from seed/portal-r02.ts.
// e is fixture-only (DV-08); d is Meera's role union with her own released K-1 (DV-09).
import { type FixtureHandler, type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { STATEMENT_PAGE_PNG } from "@abacus/ui/specimens";
import { portalHandlers } from "../handlers/portal";
import { portalK1Handlers } from "../handlers/portal-k1s";
import { seedScenario } from "../scenario";
import {
  DELIVERABLE_ID,
  PAGE_COMMENTS,
  type Por09State,
  deliverable,
  deliverables,
} from "../seed/portal-r02";

const E0 = seedScenario();
const P = "/v1/portal/deliverables";

function png(): Response {
  const raw = atob(STATEMENT_PAGE_PNG.slice(STATEMENT_PAGE_PNG.indexOf(",") + 1));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return new Response(out.buffer, {
    status: 200,
    headers: { "Content-Type": "image/png", "Cache-Control": "private, no-store" },
  });
}

function handlers(state: Por09State | "off", clock: string): Record<string, FixtureHandler> {
  const portal = { ...E0.handlers, ...portalHandlers({ clock }) };
  const base = state === "d" ? { ...portal, ...portalK1Handlers("meera_released", portal) } : portal;
  if (state === "off") {
    // A firm with `portal.deliverables` off: every deliverables read answers 404.
    return { ...base, [`GET ${P}`]: () => json({ detail: "not found" }, 404) };
  }
  return {
    ...base,
    [`GET ${P}`]: () => json(deliverables(state)),
    [`GET ${P}/{deliverable_id}`]: (r) => {
      const found = deliverable(state, r.params.deliverable_id ?? "");
      return found === undefined ? json({ detail: "not found" }, 404) : json(found);
    },
    [`GET ${P}/{deliverable_id}/versions/{version_no}/pages/{page}`]: () => png(),
    [`GET ${P}/{deliverable_id}/versions/{version_no}/comments`]: (r) =>
      json(r.params.version_no === "3" ? PAGE_COMMENTS : { items: [] }),
    [`GET ${P}/{deliverable_id}/versions/{version_no}/download`]: () => png(),
    [`POST ${P}/{deliverable_id}/versions/{version_no}/approve`]: (r) =>
      json({
        deliverable_id: r.params.deliverable_id,
        version_no: Number(r.params.version_no),
        status: "approved_by_you",
        approved_at: "2026-10-08T14:20:00Z",
      }),
  };
}

function at(state: Por09State, persona: string, clock: string): Scenario {
  return { state, persona, clock, handlers: handlers(state, clock) };
}

export const scenarios = defineScenarios({
  a: at("a", "dana-kowalski", "2026-10-06T11:10:00-05:00"),
  a2: at("a2", "dana-kowalski", "2026-10-08T09:00:00-05:00"),
  b: at("b", "dana-kowalski", "2026-10-08T16:00:00-05:00"),
  c: at("c", "dana-kowalski", "2026-10-09T10:30:00-05:00"),
  d: at("d", "meera-shah", "2026-09-15T10:00:00-05:00"),
  e: at("e", "tess-moreno", "2026-09-14T16:40:00-05:00"),
  f: at("f", "luis-ferrante", "2026-10-06T11:10:00-05:00"),
});

/** The flag-off state (not an artboard): Dana's firm with `portal.deliverables` off. */
export const FLAG_OFF: Scenario = {
  state: "off",
  persona: "dana-kowalski",
  clock: "2026-10-06T11:10:00-05:00",
  handlers: handlers("off", "2026-10-06T11:10:00-05:00"),
};

/** What an artboard opens with: a on page 2, a2 with the approve confirm, c on the report. */
export const OPENING: Readonly<
  Partial<Record<Por09State, { page?: number; confirming?: boolean; deliverableId?: string }>>
> = {
  a: { page: 2 },
  a2: { confirming: true },
  c: { deliverableId: DELIVERABLE_ID.report },
};

export type { Por09State };
export const STATES = Object.keys(scenarios) as Por09State[];
