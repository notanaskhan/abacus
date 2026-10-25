// P-09-T09 (SHL-13 first slice): runs as tool cards, expanding follows the run, Open trace opens
// WB-09, and nothing here decides anything.
import type { AgentRunOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { json, mockApi, renderRoutes } from "../../testing/support";
import { AgentDock, proposedWords } from "./AgentDock";

const E = "e-1";
const RUN: AgentRunOut = {
  id: "r-1",
  agent: "evidence.screener",
  agent_label: "Evidence screener",
  state: "succeeded",
  started_at: "2026-10-26T09:00:00Z",
  finished_at: "2026-10-26T09:00:04Z",
  duration_ms: 4200,
  initiator_name: "Dana Leader",
  subject: "evidence_version",
};

afterEach(cleanup);

function renderOne(component: () => JSX.Element): void {
  renderRoutes([{ path: "/", component }]);
}

describe("SHL-13 agent dock", () => {
  it("words the tool card's proposal counts", () => {
    expect(proposedWords("citations:2,unverified:0")).toBe("2 citations, 0 unverified");
    expect(proposedWords(null)).toBeNull();
  });

  it("shows runs as tool cards and expands one with what it read and proposed", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/agent-runs`]: () => json([RUN]),
      [`GET /v1/agent-runs/r-1/items`]: () =>
        json({
          run: RUN,
          items: [
            {
              seq: 1,
              kind: "tool_card",
              at: RUN.started_at,
              code: "evidence.screener",
              outcome: "succeeded",
              detail: "citations:2",
              actor: null,
              ref_type: "evidence_version",
              ref_id: "v-1",
            },
            {
              seq: 2,
              kind: "decision",
              at: RUN.finished_at,
              code: "accepted",
              outcome: null,
              detail: "screening",
              actor: "Sam Staff",
              ref_type: "screening_result",
              ref_id: "s-1",
            },
          ],
          last_seq: 2,
          resync: false,
        }),
    });
    renderOne(() => (
      <AgentDock engagementId={E}>
        <p>activity below</p>
      </AgentDock>
    ));
    const title = await screen.findByRole("button", { name: "Execute › screen evidence" });
    expect(screen.getByText("Finished")).toBeTruthy();
    expect(screen.getByText("activity below")).toBeTruthy();
    fireEvent.click(title);
    expect(await screen.findByText("2 citations")).toBeTruthy();
    expect(await screen.findByText("accepted by Sam Staff")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /approve|decide|sign off/i })).toBeNull();
  });

  it("opens the trace drawer", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/agent-runs`]: () => json([RUN]),
      [`GET /v1/agent-runs/r-1/trace`]: () =>
        json({
          run: RUN,
          runtime: "Accrued Agent runtime",
          region: "United States (data and inference)",
          training: "Firm data is never used for training",
          attempts: 1,
          tokens_in: 10,
          tokens_out: 5,
          rows: [],
          records_read: [],
          output_counts: [],
          model_text: null,
          projection: "content",
        }),
    });
    renderOne(() => <AgentDock engagementId={E} />);
    fireEvent.click(await screen.findByRole("button", { name: "Open trace" }));
    expect(await screen.findByText("Accrued Agent runtime")).toBeTruthy();
  });

  it("says when there are no runs, and stays out of the way when refused", async () => {
    mockApi({ [`GET /v1/engagements/${E}/agent-runs`]: () => json([]) });
    renderOne(() => <AgentDock engagementId={E} />);
    expect(await screen.findByText("No runs yet")).toBeTruthy();
    cleanup();
    mockApi({ [`GET /v1/engagements/${E}/agent-runs`]: () => json({ detail: "forbidden" }, 403) });
    renderOne(() => (
      <AgentDock engagementId={E}>
        <p>activity below</p>
      </AgentDock>
    ));
    expect(await screen.findByText("activity below")).toBeTruthy();
    expect(screen.queryByText("No runs yet")).toBeNull();
  });
});
