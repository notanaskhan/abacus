// C6 v1.1's fixture routes (P-09-T01; TASK-6201): the run, its feed, trace, records read and writes
// for the four E0 runs. The step detail answers 404 as the live route does while `run_trace.enabled`
// is off. A scenario mounts these beside its own handlers (SHL-13 and WB-09 from P-09-T09/T10).
import type { RunItemsOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { SHL13_RUNS } from "../seed/agent-dock";
import { E0_RUNS, type E0Run } from "../seed/agent-runs";

const ALL_RUNS: Record<string, E0Run> = { ...E0_RUNS, ...SHL13_RUNS };

const NOT_FOUND = { detail: "not_found" };

function runOf(params: Record<string, string | undefined>): E0Run | undefined {
  return ALL_RUNS[params.run_id ?? ""];
}

export function agentRunHandlers(
  runs: Record<string, E0Run> = ALL_RUNS,
): Record<string, FixtureHandler> {
  const find = (params: Record<string, string | undefined>) =>
    runs[params.run_id ?? ""] ?? runOf(params);
  return {
    "GET /v1/agent-runs/{run_id}": ({ params }) => {
      const run = find(params);
      return run === undefined ? json(NOT_FOUND, 404) : json(run.view);
    },
    "GET /v1/agent-runs/{run_id}/items": ({ params, query }) => {
      const run = find(params);
      if (run === undefined) return json(NOT_FOUND, 404);
      const after = Number(query.get("after_seq") ?? "0");
      const items = run.items.filter((i) => i.seq > after);
      const last = run.items.reduce((n, i) => Math.max(n, i.seq), 0);
      return json({
        run: run.view.run,
        items,
        last_seq: last,
        next_seq: last,
        resync: false,
      } satisfies RunItemsOut);
    },
    "GET /v1/agent-runs/{run_id}/trace": ({ params }) => {
      const run = find(params);
      return run === undefined ? json(NOT_FOUND, 404) : json(run.trace);
    },
    "GET /v1/agent-runs/{run_id}/trace/records-read": ({ params }) => {
      const run = find(params);
      return run === undefined ? json(NOT_FOUND, 404) : json(run.recordsRead);
    },
    "GET /v1/agent-runs/{run_id}/trace/writes": ({ params }) => {
      const run = find(params);
      return run === undefined ? json(NOT_FOUND, 404) : json(run.writes);
    },
    "GET /v1/agent-runs/{run_id}/trace/steps/{step_id}": () => json(NOT_FOUND, 404),
  };
}
