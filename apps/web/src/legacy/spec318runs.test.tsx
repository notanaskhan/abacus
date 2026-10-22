// SPEC-318 (TASK-461): the agent run list, the trace drawer and the JSON export.
import type { AgentRunOut, RunTraceOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes } from "../testing/support";
import { AgentRuns, duration } from "./AgentRuns";

const E = "e-1";
const RUN: AgentRunOut = {
  id: "r-1",
  agent: "evidence.screener",
  agent_label: "Evidence screener",
  state: "needs_input",
  started_at: "2026-10-22T09:00:00Z",
  finished_at: "2026-10-22T09:00:04Z",
  duration_ms: 4200,
  initiator_name: "Dana Leader",
  subject: "evidence_version",
};
const TRACE: RunTraceOut = {
  run: RUN,
  runtime: "Abacus agent runtime",
  region: "United States (data and inference)",
  training: "Firm data is never used for training",
  attempts: 2,
  tokens_in: 900,
  tokens_out: 120,
  rows: [
    {
      seq: 1,
      at: RUN.started_at,
      kind: "start",
      title: "Run started",
      state: "done",
      detail: "requested",
      actor: "Dana Leader",
    },
    {
      seq: 2,
      at: RUN.started_at,
      kind: "attempt",
      title: "Model call",
      state: "failed",
      detail: "timeout",
      actor: null,
    },
    {
      seq: 3,
      at: RUN.started_at,
      kind: "finish",
      title: "Needs a person",
      state: "waiting",
      detail: null,
      actor: null,
    },
  ],
  records_read: [{ source: "evidence_version", count: 1 }],
  output_counts: [{ kind: "citations", count: 2 }],
  model_text: "The invoice total matches the ledger.",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderOne(component: () => JSX.Element): void {
  renderRoutes([{ path: "/", component }]);
}

describe("SPEC-318 agent runs", () => {
  it("formats durations without locale calls (ac2)", () => {
    expect(duration(850)).toBe("850 ms");
    expect(duration(4200)).toBe("4.2 s");
    expect(duration(185_000)).toBe("3 min 5 s");
    expect(duration(null)).toBe("—");
  });

  it("lists runs and opens a trace with its timeline and the agent's words (ac1, ac3)", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/agent-runs`]: () => json([RUN]),
      [`GET /v1/agent-runs/r-1/trace`]: () => json(TRACE),
    });
    renderOne(() => <AgentRuns engagementId={E} />);
    expect(await screen.findByText("Evidence screener")).toBeTruthy();
    expect(screen.getAllByText("Needs a person").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Open trace" }));
    expect(await screen.findByText("Model call")).toBeTruthy();
    expect(screen.getByText("timeout")).toBeTruthy();
    expect(screen.getByText("The invoice total matches the ledger.")).toBeTruthy();
    expect(screen.getByText("2 citations")).toBeTruthy();
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("exports the trace as JSON (ac6)", async () => {
    const created = vi.fn(() => "blob:x");
    vi.stubGlobal(
      "URL",
      Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() }),
    );
    const api = mockApi({
      [`GET /v1/engagements/${E}/agent-runs`]: () => json([RUN]),
      [`GET /v1/agent-runs/r-1/trace`]: () => json(TRACE),
      [`POST /v1/agent-runs/r-1/trace-exports`]: () =>
        json(
          {
            filename: "run-trace-r-1.json",
            content: "{}",
            sha256: "a".repeat(64),
            rows: 3,
            renderer_version: "trace-v1",
          },
          201,
        ),
    });
    renderOne(() => <AgentRuns engagementId={E} />);
    fireEvent.click(await screen.findByRole("button", { name: "Open trace" }));
    await screen.findByText("Model call");
    fireEvent.click(screen.getByRole("button", { name: "Export JSON" }));
    await waitFor(() => {
      expect(created).toHaveBeenCalled();
    });
    expect(api.calls.find((c) => c.method === "POST")?.body).toEqual({ format: "json" });
  });

  it("shows the empty state and hides itself when not allowed (ac5)", async () => {
    mockApi({ [`GET /v1/engagements/${E}/agent-runs`]: () => json([]) });
    renderOne(() => <AgentRuns engagementId={E} />);
    expect(await screen.findByText("No runs yet")).toBeTruthy();
    cleanup();
    mockApi({ [`GET /v1/engagements/${E}/agent-runs`]: () => json({ detail: "forbidden" }, 403) });
    renderOne(() => <AgentRuns engagementId={E} />);
    await waitFor(() => {
      expect(screen.queryByText("Agent runs")).toBeNull();
    });
  });
});
