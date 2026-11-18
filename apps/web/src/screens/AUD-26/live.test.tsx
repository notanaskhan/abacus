// A-08-T32 (TASK-8547; DEC-5531): AUD-26 live draws the server's SSARS workspace: its rail in the
// server's order and states (an unknown state reads Not started), its mode, and in review mode the
// analytics set's statement.
import type { AnalyticsSetOut, SsarsWorkspaceOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { GRANITE_PEAK_LINES } from "../../fixtures/seed/fieldwork";
import { newQueryClient } from "../../testing/support";
import { AUD26Live, stepOf } from "./live";

const WORK_ITEM = "00000000-0000-4000-8000-0000000a2601";
const SET_ID = "00000000-0000-4000-8000-0000000a2602";

const workspace: SsarsWorkspaceOut = {
  mode: "review",
  standard: "AR-C 90",
  legend: null,
  analytics_set_id: SET_ID,
  approval_label: null,
  inquiries: { answered: 0, open: 0, questionnaire_id: null },
  report_available: false,
  rail: [
    { key: "inquiries", label: "Inquiries", state: "done" },
    { key: "analytics", label: "Analytics", state: "in_progress" },
    { key: "report", label: "Report", state: "unknown_state" },
  ],
};

const set: AnalyticsSetOut = {
  id: SET_ID,
  kind: "ssars_review",
  stage: "review",
  status: "computed" as AnalyticsSetOut["status"],
  basis_label: "FY2026 vs FY2025",
  engine_version: "flux-1",
  inputs_hash: "a".repeat(64),
  version_no: 1,
  lines: GRANITE_PEAK_LINES,
  tallies: { lines: 14, over_threshold: 8, explained: 6, unexplained: 2, tb_balanced: true },
  threshold: {
    pct: "10",
    amount: "116250.00",
    provisional: false,
    decider_name: null,
    materiality_version_id: null,
    overall_materiality: null,
  },
  allowed_actions: [],
};

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

describe("AUD-26 live", () => {
  it("keeps the server's step states and reads an unknown one as Not started", () => {
    expect(workspace.rail.map(stepOf).map((s) => s.state)).toEqual([
      "done",
      "in_progress",
      "not_started",
    ]);
  });

  it("draws the review workspace with its analytics statement", async () => {
    restore = installFixtureMode({
      state: "live",
      handlers: {
        "GET /v1/work-items/{work_item_id}/ssars": () => json(workspace),
        "GET /v1/analytics-sets/{analytics_set_id}": () => json(set),
      },
    });
    render(
      <QueryClientProvider client={newQueryClient()}>
        <AUD26Live workItemId={WORK_ITEM} />
      </QueryClientProvider>,
    );
    await waitFor(() => {
      expect(document.querySelector("[data-aud13='statement']")).not.toBeNull();
    });
    expect(document.querySelector("[data-screen='AUD-26']")?.getAttribute("data-mode")).toBe(
      "review",
    );
    expect(document.querySelector("[data-aud26='standard']")?.textContent).toBe("AR-C 90");
  });
});
