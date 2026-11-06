// A-04-T38 (TASK-3325): AUD-10's keyboard rule. The CUEC rows are buttons in tab order and the gap is
// a named button. Tier C locks and axe run through Playwright in the end pass; the row's results are
// recorded in docs/plan/status/S28-end-pass.md.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { scenarios } from "./scenarios";
import { useServiceOrgsCanvas } from "./ServiceOrgs";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function Canvas(): JSX.Element {
  return <div>{useServiceOrgsCanvas("00000000-0000-4000-8000-000000000001", {}).children}</div>;
}

describe("AUD-10 keyboard", () => {
  it("reaches each CUEC and the gap by name", async () => {
    restore = installFixtureMode(scenarios.a);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Canvas />
      </QueryClientProvider>,
    );
    await waitFor(() => {
      expect(document.querySelectorAll("[data-cuec]")).toHaveLength(6);
    });
    for (const row of document.querySelectorAll<HTMLButtonElement>("[data-cuec]")) {
      expect(row.tagName).toBe("BUTTON");
      expect(row.tabIndex).toBeGreaterThanOrEqual(0);
    }
    expect(document.querySelector("[data-aud10='gap']")?.getAttribute("aria-label")).toBe(
      "Gap · 92 days",
    );
  });
});
