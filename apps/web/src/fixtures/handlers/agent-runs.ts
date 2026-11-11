// C6 v1.1's fixture routes (P-09-T01; TASK-6201): the run, its feed, trace, records read and writes
// for the four E0 runs. The step detail answers 404 as the live route does while `run_trace.enabled`
// is off. A scenario mounts these beside its own handlers (SHL-13 and WB-09 from P-09-T09/T10).
import type { RunItemsOut, RunPlanOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { SHL13_RUNS } from "../seed/agent-dock";
import { DEMO_MS } from "../seed/clock";
import {
  E0_RUNS,
  type E0Run,
  LIST_RETURNS_SAMPLES,
  LIST_RETURNS_STEP_ID,
} from "../seed/agent-runs";

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
  // P-09-T19 (j03 6): a plan a person approved in this page's life. The run then reads
  // `dispatched` with nothing blocking it, as C6 v2's approve answers (P-10-T33).
  const approved = new Map<string, string>();
  return {
    "GET /v1/agent-runs/{run_id}": ({ params }) => {
      const run = find(params);
      if (run === undefined) return json(NOT_FOUND, 404);
      if (!approved.has(run.view.run.id)) return json(run.view);
      return json({
        ...run.view,
        run: { ...run.view.run, state: "dispatched" },
        ...(run.view.header == null ? {} : { header: { ...run.view.header, blocked_on: null } }),
      });
    },
    "POST /v1/agent-runs/{run_id}/plan/approve": ({ params, body, persona }) => {
      const run = find(params);
      if (run === undefined) return json(NOT_FOUND, 404);
      const header = run.view.header;
      const waiting =
        run.view.run.state === "needs_input" && header?.blocked_on?.kind === "approval";
      const expected = (body as { expected_version?: unknown } | null)?.expected_version;
      if (!waiting || approved.has(run.view.run.id))
        return json({ detail: "run_not_waiting" }, 409);
      if (header.plan_version == null || expected !== header.plan_version) {
        return json({ detail: "plan_changed" }, 409);
      }
      // The fixture decides at the scenario's instant (9:24 AM), as its clock stands.
      const at = new Date(DEMO_MS).toISOString();
      approved.set(run.view.run.id, at);
      return json({
        id: `${run.view.run.id}:plan:${String(header.plan_version)}`,
        run_id: run.view.run.id,
        state: "approved",
        version: header.plan_version,
        steps: header.plan_steps ?? [],
        decided_at: at,
        decided_by: persona ?? null,
      } satisfies RunPlanOut);
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
    // WB-09 a2: the one expandable row the handoff draws ("Execute › list returns": the summarised
    // arguments and the first five returns it read, from the TAX-02 seed).
    "GET /v1/agent-runs/{run_id}/trace/steps/{step_id}": ({ params }) =>
      params.step_id === LIST_RETURNS_STEP_ID
        ? json({
            step_id: LIST_RETURNS_STEP_ID,
            title: "Execute › list returns",
            args_summary: "tax year 2025",
            records_read: 224,
            samples: LIST_RETURNS_SAMPLES,
          })
        : json(NOT_FOUND, 404),
  };
}
