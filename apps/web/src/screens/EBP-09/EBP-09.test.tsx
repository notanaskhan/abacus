// A-05-T45 (TASK-5125): EBP-09 in fixture mode. Row: "Clicking a cell shows its citations in the
// footer, and each tally's scope label says which tab its exception count covers."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { EBP09_WORK_ITEM } from "../../fixtures/seed/ebp09";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { useExpensesCanvas } from "./Expenses";
import { type Ebp09State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

type Tab = "expenses" | "compliance" | "qualification";

function Canvas({ tab }: { tab: Tab }): JSX.Element {
  const canvas = useExpensesCanvas(EBP09_WORK_ITEM, { tab });
  return <div>{canvas.children}</div>;
}

function show(state: Ebp09State, tab: Tab = "expenses"): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Canvas tab={tab} />
    </QueryClientProvider>,
  );
}

describe("EBP-09", () => {
  it("a: the grid foots and a cell shows its citations in the footer", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelector('[data-grid="expenses"]')).not.toBeNull();
    });
    const grid = document.querySelector('[data-grid="expenses"]');
    expect(grid?.textContent).toContain("$38,400.00");
    const cited = document.querySelector('[data-cell="G4"]');
    expect(cited).not.toBeNull();
    fireEvent.click(cited as Element);
    expect(document.querySelector("[data-footer]")?.textContent).toBe(
      "G4 · 2 citations: Brightwater Hale invoice 2025-0412 · Keystone ERISA budget statement Q2 2025",
    );
  });

  it.each([
    ["expenses", COPY.tally.scopeExpenses],
    ["compliance", COPY.tally.scopeCompliance],
    ["qualification", COPY.tally.scopeQualification],
  ] as const)("%s: the tally says which tab its count covers", async (tab, scope) => {
    show("a", tab);
    await waitFor(() => {
      expect(document.querySelector('[data-tally="exceptions"]')).not.toBeNull();
    });
    expect(document.querySelector('[data-tally="exceptions"]')?.textContent).toContain(scope);
  });

  it("b: the only compliance exception is missed auto-enrollment, on 2025 limits", async () => {
    show("b", "compliance");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-test-key]")).toHaveLength(9);
    });
    const exceptions = [...document.querySelectorAll("[data-test-key]")].filter((r) =>
      r.textContent.includes(COPY.exception),
    );
    expect(exceptions.map((r) => r.getAttribute("data-test-key"))).toEqual(["auto_enrollment"]);
    expect(document.body.textContent).toContain("$23,500; catch-up $7,500; ages 60–63 $11,250");
  });

  it("c: plan qualification lists its facts", async () => {
    show("c", "qualification");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-fact]")).toHaveLength(7);
    });
  });

  it("d: an expense with no disclosure offers Raise exception", async () => {
    show("d");
    await waitFor(() => {
      expect(document.querySelector("[data-exception]")).not.toBeNull();
    });
    expect(document.querySelector("[data-exception]")?.textContent).toContain(
      "No disclosure on file for $1,200.00",
    );
  });
});
