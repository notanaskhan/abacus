// A-03-T12 · AUD-06 groups Granite Peak's lines by grouping › FS line once the mapping set is
// confirmed: the groups are the mapping's groupings under the server's subtotals; nothing is summed
// in the browser.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { AUD06Frame } from "./artboard";
import { scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

describe("AUD-06 by FS line (A-03-T12)", () => {
  it("groups Granite Peak's lines by the confirmed mapping's groupings", async () => {
    restore = installFixtureMode(scenarios.fs_line);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <AUD06Frame state="fs_line" />
      </QueryClientProvider>,
    );
    await screen.findByRole("table");
    await waitFor(() => {
      const groups = [...document.querySelectorAll("tr[data-group]")].map((g) => g.textContent);
      expect(groups).toContain("Debt");
    });
    const groups = [...document.querySelectorAll("tr[data-group]")].map((g) => g.textContent);
    expect(groups[0]).toBe("Cash");
    expect(groups).not.toContain("Accounts");
    expect(groups).toHaveLength(13);
  });

  it("h (no mapping read): the trial balance keeps its own grouping", async () => {
    restore = installFixtureMode(scenarios.h);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <AUD06Frame state="h" />
      </QueryClientProvider>,
    );
    await screen.findByRole("table");
    const groups = [...document.querySelectorAll("tr[data-group]")].map((g) => g.textContent);
    expect(groups).toEqual(["Accounts"]);
  });
});
