// A-08-T32 (TASK-8546; DEC-5531): AUD-13 live draws the server's set: its lines in the statement
// grammar, its tallies and dual threshold, and offers Accept explanations… only when the set's
// `allowed_actions` holds `analytics.accept`, posting the explained lines against `review_hash`.
import type { AnalyticsSetOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { GRANITE_PEAK_LINES } from "../../fixtures/seed/fieldwork";
import { newQueryClient } from "../../testing/support";
import { AUD13Live } from "./live";

const SET_ID = "00000000-0000-4000-8000-0000000a1301";

const set = (allowed: AnalyticsSetOut["allowed_actions"]): AnalyticsSetOut => ({
  id: SET_ID,
  kind: "audit_flux",
  stage: "preliminary",
  status: "computed" as AnalyticsSetOut["status"],
  basis_label: "Interim 6/30/2026 vs 6/30/2025",
  engine_version: "flux-1",
  inputs_hash: "a".repeat(64),
  review_hash: "b".repeat(64),
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
  allowed_actions: allowed,
});

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
let posted: unknown = null;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  posted = null;
});

function show(allowed: AnalyticsSetOut["allowed_actions"]): void {
  restore = installFixtureMode({
    state: "live",
    handlers: {
      "GET /v1/analytics-sets/{analytics_set_id}": () => json(set(allowed)),
      "POST /v1/analytics-sets/{analytics_set_id}/explanations/accept": ({ body }) => {
        posted = body;
        return json(set(allowed));
      },
    },
  });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AUD13Live analyticsSetId={SET_ID} />
    </QueryClientProvider>,
  );
}

describe("AUD-13 live", () => {
  it("draws every line of the set and the server's tallies and threshold", async () => {
    show([]);
    await waitFor(() => {
      expect(document.querySelector("[data-aud13='statement']")).not.toBeNull();
    });
    const drawn = document.querySelectorAll("[data-line], [data-subtotal]").length;
    expect(drawn).toBe(GRANITE_PEAK_LINES.length);
    const tallies = document.querySelector("[data-aud13='tallies']")?.textContent ?? "";
    expect(tallies).toContain("10% and $116,250");
    expect(screen.queryByRole("button", { name: "Accept explanations…" })).toBeNull();
  });

  it("a manager accepts the explained lines against the set's review hash", async () => {
    show(["analytics.accept"]);
    const button = await screen.findByRole("button", { name: "Accept explanations…" });
    fireEvent.click(button);
    await waitFor(() => {
      expect(posted).not.toBeNull();
    });
    const explained = GRANITE_PEAK_LINES.filter((l) => l.status === "explained").map(
      (l) => l.position,
    );
    expect(posted).toEqual({ line_positions: explained, seen_hash: "b".repeat(64) });
  });
});
