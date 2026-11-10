// POR-08 · Approvals a–f (R-02-T19; docs/screens/POR-08.md): the personas and clocks of the screen
// contract on the portal handlers, answering the approvals reads from seed/portal-por08.ts. a–d are
// fixture-only (DV-08: no provider registers `fs_package` yet); e, e2 and f run live.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { portalHandlers } from "../handlers/portal";
import { seedScenario } from "../scenario";
import { type Por08State, approvalDetail, approvals } from "../seed/portal-por08";

const E0 = seedScenario();
const P = "/v1/portal/approvals";

function decided(state: string): Response {
  return json({ state, decided_at: "2026-09-25T15:02:00Z" });
}

function handlers(state: Por08State | "off", clock: string): Record<string, FixtureHandler> {
  const base = { ...E0.handlers, ...portalHandlers({ clock }) };
  if (state === "off") {
    // A firm with `portal.approvals` off: every approvals read answers 404.
    return { ...base, [`GET ${P}`]: () => json({ detail: "not found" }, 404) };
  }
  return {
    ...base,
    [`GET ${P}`]: (r) => json(approvals(state, r.query.get("filter"))),
    [`GET ${P}/{kind}/{item_id}`]: (r) => {
      const found = approvalDetail(state, r.params.item_id ?? "");
      return found === undefined ? json({ detail: "not found" }, 404) : json(found);
    },
    [`GET ${P}/{kind}/{item_id}/questions`]: () => json({ items: [] }),
    [`POST ${P}/{kind}/{item_id}/questions`]: (r) =>
      json({
        id: `question-${r.params.item_id ?? ""}`,
        author: "Ben Ashby",
        body: (r.body as { body?: string } | undefined)?.body ?? "",
        created_at: "2026-09-14T21:41:00Z",
      }),
    [`POST ${P}/proposed-entries/{entry_id}/decide`]: (r) =>
      decided(
        (r.body as { decision?: string } | undefined)?.decision === "accept"
          ? "accepted"
          : "not_recorded",
      ),
    [`POST ${P}/uncorrected-misstatements/{item_id}/acknowledge`]: () => decided("acknowledged"),
    [`POST ${P}/packages/{package_id}/decide`]: (r) =>
      decided(
        (r.body as { decision?: string } | undefined)?.decision === "approve"
          ? "approved"
          : "declined",
      ),
    [`GET ${P}/{kind}/{item_id}/journal`]: () => json({ render_job_id: "journal-1" }, 202),
  };
}

function at(state: Por08State, persona: string, clock: string): Scenario {
  return { state, persona, clock, handlers: handlers(state, clock) };
}

const SEP_14 = "2026-09-14T16:40:00-05:00";

export const scenarios = defineScenarios({
  a: at("a", "ben-ashby", SEP_14),
  a2: at("a2", "ben-ashby", SEP_14),
  b: at("b", "tess-moreno", "2026-09-15T08:42:00-05:00"),
  c: at("c", "ben-ashby", SEP_14),
  d: at("d", "ben-ashby", SEP_14),
  e: at("e", "dana-kowalski", "2026-09-24T10:00:00-05:00"),
  e2: at("e2", "dana-kowalski", "2026-09-25T10:00:00-05:00"),
  f: at("f", "ben-ashby", SEP_14),
});

/** The flag-off state (not an artboard): Ben's firm with the approvals flag off. */
export const FLAG_OFF: Scenario = {
  state: "off",
  persona: "ben-ashby",
  clock: SEP_14,
  handlers: handlers("off", SEP_14),
};

/** What an artboard opens with: a2 the approve confirm, c the decline sheet, d the composer on
 * the 14,900 entry (expanded). */
export const OPENING: Readonly<
  Partial<Record<Por08State, { overlay?: "confirm" | "decline" | "ask"; expanded?: number }>>
> = {
  a: { expanded: 4 },
  a2: { overlay: "confirm" },
  c: { overlay: "decline" },
  d: { overlay: "ask", expanded: 4 },
};

export type { Por08State };
export const STATES = Object.keys(scenarios) as Por08State[];
