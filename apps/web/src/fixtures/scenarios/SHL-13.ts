// SHL-13 and WB-09 for parity and accessibility (P-09-T18; P-09 §5.4–5.5): the E0 seed with the
// fixture runs' routes and the three flags the dock and drawer sit behind. SHL-13's state board is
// the handoff's eight 330 × 733 docks, each a run from seed/agent-dock.ts; WB-09's artboards are the
// trace drawer on the four E0 runs. Every figure is the fixture runs' (P-09-T12), never the kit's.
import { type Scenario, json } from "../../app-core/fixture-mode";
import { agentRunHandlers } from "../handlers/agent-runs";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  RUN_4127_ASK_ID,
  RUN_4127_DONE_ID,
  RUN_4127_FAILED_ID,
  RUN_4127_IDLE_ID,
  RUN_4127_PLAN_ID,
  RUN_CLOSE_COPPERLEAF_ID,
} from "../seed/agent-dock";
import { RUN_4118_ID, RUN_4127_ID, RUN_AUG17_ID, RUN_COPPERLEAF_2_ID } from "../seed/agent-runs";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const FLAGS = ["agent_runtime.v2", "agent_dock.enabled", "run_trace.enabled"] as const;
export const AGENT_CLOCK = "2026-09-14T09:24:00-05:00";

/** The board's eight docks in the handoff's order, each with its caption and run. */
export const DOCKS: readonly { n: number; caption: string; runId: string }[] = [
  { n: 1, caption: "Idle · 9:20 AM", runId: RUN_4127_IDLE_ID },
  { n: 2, caption: "Plan proposed · 9:23 AM", runId: RUN_4127_PLAN_ID },
  { n: 3, caption: "Running · 9:41 AM", runId: RUN_4127_ID },
  { n: 4, caption: "Blocked on decision", runId: RUN_4127_ID },
  { n: 5, caption: "Needs your answer · Sampling", runId: RUN_4127_ASK_ID },
  { n: 6, caption: "Failed step · 9:58 AM", runId: RUN_4127_FAILED_ID },
  { n: 7, caption: "Completed · Fri 2 Oct, 4:05 PM", runId: RUN_4127_DONE_ID },
  { n: 8, caption: "Close variant · Copperleaf, Run 2", runId: RUN_CLOSE_COPPERLEAF_ID },
];

export type Wb09State = "a" | "a2" | "a3" | "a4" | "b" | "c" | "d" | "e";

/** WB-09's artboards: the run and the drawer's view (a3 Records read, a4 Writes & approvals). */
export const WB09: Readonly<
  Record<Wb09State, { runId: string; view?: "Records read" | "Writes & approvals" }>
> = {
  a: { runId: RUN_4118_ID },
  a2: { runId: RUN_4118_ID },
  a3: { runId: RUN_4118_ID, view: "Records read" },
  a4: { runId: RUN_4118_ID, view: "Writes & approvals" },
  b: { runId: RUN_4127_ID },
  c: { runId: RUN_AUG17_ID },
  d: { runId: RUN_COPPERLEAF_2_ID },
  e: { runId: RUN_4118_ID },
};
export const WB09_STATES = Object.keys(WB09) as Wb09State[];

/** The agent surfaces' scenario: the seed, the runs' routes and the flags on, as Hannah Leclerc.
 * `loading` holds the trace unanswered (WB-09e); `forbidden` answers 403 (not allowed). */
export function agentScenario(state: string, loading = false, forbidden = false): Scenario {
  const seed = getSeed();
  const runs = agentRunHandlers();
  return {
    state,
    persona: "hannah-leclerc",
    clock: AGENT_CLOCK,
    handlers: {
      ...E0.handlers,
      ...runs,
      ...(loading
        ? { "GET /v1/agent-runs/{run_id}/trace": () => new Promise<Response>(() => undefined) }
        : {}),
      // P-09-T19 (j18 5): a person `agent_run.read` refuses (Lena Park, seasonal) reads 403.
      ...(forbidden
        ? {
            "GET /v1/agent-runs/{run_id}/trace": () => json({ detail: "forbidden" }, 403),
            "GET /v1/agent-runs/{run_id}": () => json({ detail: "forbidden" }, 403),
          }
        : {}),
      "GET /v1/me/capabilities": ({ persona }) => {
        const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
        const on = Object.fromEntries(FLAGS.map((f) => [f, true]));
        return json({ ...base, flags: { ...base.flags, ...on } });
      },
    },
  };
}

/** A-01-T33: a host's scenario with the dock live: the fixture runs' routes beside its own, and
 * the three agent flags added to whatever capabilities it answers (AUD-02's cockpit flag kept). */
export function withAgentDock(scenario: Scenario): Scenario {
  const runs = agentRunHandlers();
  const read = scenario.handlers["GET /v1/me/capabilities"];
  return {
    ...scenario,
    handlers: {
      ...runs,
      ...scenario.handlers,
      "GET /v1/me/capabilities": async (request) => {
        const answer =
          read === undefined
            ? json(capabilitiesFor(getSeed(), request.persona ?? "hannah-leclerc"))
            : await read(request);
        if (!answer.ok) return answer;
        const body = (await answer.json()) as { flags?: Record<string, unknown> };
        const on = Object.fromEntries(FLAGS.map((f) => [f, true]));
        return json({ ...body, flags: { ...body.flags, ...on } });
      },
    },
  };
}

/** A-01-T33: the run AUD-02's run artboards open in the dock (b and g have none; f is the O3). */
export const AUD02_DOCK_RUN: Readonly<Record<string, string>> = {
  a: RUN_4127_ID,
  c: RUN_4127_PLAN_ID,
  d: RUN_4127_ID,
  e: RUN_4127_FAILED_ID,
};
