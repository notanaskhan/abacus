// KNW-02 a, a2 and b (K-01-T23; K-01 §3.7 AC7.1 to AC7.3). Acceptance: "KNW-02a, a2 and b pass
// Tier C, and selecting step 4 lights page 14 while selecting the page region lights the row."
// Tier C is the visual suite's; here the sheet rows carry their page's match key, the ⚑ filter
// shows only step 7 (split pp. 15–16) with Confirm, and b's RunCard reads the import's counts.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { KNW02, type Knw02Search } from ".";
import { type Knw02State, OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function Page({ state }: { state: Knw02State }): JSX.Element {
  const opens = OPENS[state];
  const [search, setSearch] = useState<Knw02Search>(
    opens.flagged === true ? { flagged: true } : {},
  );
  return <KNW02 versionId={opens.versionId} search={search} onSearch={setSearch} />;
}

function show(state: Knw02State): { method: string; path: string; body: unknown }[] {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Page state={state} />
    </QueryClientProvider>,
  );
  return calls;
}

async function rows(): Promise<HTMLElement> {
  return waitFor(() => {
    const found = document.querySelector<HTMLElement>('[data-knw02="import-steps"]');
    if (found === null) throw new Error("no imported steps");
    return found;
  });
}

describe("KNW-02 a · Needs review, step 4 on p. 14", () => {
  it("every parsed step cites a page; step 4's row and the p. 14 region share one match key", async () => {
    show("a");
    const table = await rows();
    const step4 = table.querySelector<HTMLElement>('[data-step="4"]');
    expect(step4).not.toBeNull();
    expect(within(step4 as HTMLElement).getByText("p. 14")).toBeTruthy();
    const key = step4?.getAttribute("data-match") ?? "";
    expect(key).toMatch(/-p14$/);
    // Both ways: the viewer's region for p. 14 carries the same key the row binds.
    await waitFor(() => {
      const regions = [...document.querySelectorAll<HTMLElement>("[data-match]")].filter(
        (el) => el.getAttribute("data-match") === key,
      );
      expect(regions.length).toBeGreaterThanOrEqual(2);
    });
    for (const row of table.querySelectorAll("[data-step]")) {
      expect(row.textContent).toMatch(/pp?\. \d+/);
    }
  });

  it("shows the Uploaded files group and the ⚑ Flagged tab", async () => {
    show("a");
    await rows();
    expect(screen.getByText("Uploaded files")).toBeTruthy();
    expect(screen.getAllByText("⚑ Flagged").length).toBeGreaterThan(0);
  });
});

describe("KNW-02 a2 · the ⚑ filter", () => {
  it("shows only step 7, split pp. 15–16, and Confirm posts the step's row version", async () => {
    const calls = show("a2");
    const table = await rows();
    const shown = [...table.querySelectorAll<HTMLElement>("[data-step]")];
    expect(shown.map((r) => r.getAttribute("data-step"))).toEqual(["7"]);
    const step7 = shown[0] as HTMLElement;
    expect(step7.getAttribute("data-flagged")).toBe("true");
    expect(within(step7).getByText("pp. 15–16")).toBeTruthy();
    fireEvent.click(within(step7).getByRole("button", { name: "Confirm" }));
    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST" && c.path.endsWith("/flag-resolution"));
      const body = post?.body as { action?: string; row_version?: unknown } | undefined;
      expect(body?.action).toBe("confirm");
      expect(typeof body?.row_version).toBe("number");
    });
    await waitFor(() => {
      expect(document.querySelectorAll('[data-knw02="import-steps"] [data-step]').length).toBe(0);
    });
  });
});

describe("KNW-02 b · Parsing", () => {
  it("the RunCard reads 2 files and 41 of 96 pages, and the viewer waits", async () => {
    show("b");
    const card = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-knw02="run-card"]');
      if (found === null) throw new Error("no run card");
      return found;
    });
    expect(card.textContent).toContain("Methodology importer is reading 2 files");
    expect(card.textContent).toContain("41 of 96 pages");
  });
});
