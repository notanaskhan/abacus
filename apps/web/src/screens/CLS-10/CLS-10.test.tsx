// C-01-T40 (TASK-8420): CLS-10 Flux a–e in fixture mode. Row acceptance: "Only Payroll and Repairs
// carry the over-both-legs cell, Accept is absent for Raj Malhotra, and year over year never shows
// an invented value."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { copperleafFluxAt } from "../../fixtures/seed/close-book";
import { CLOSE_IDS } from "../../fixtures/seed/closes";
import { newQueryClient } from "../../testing/support";
import { CLS10, percent, talliesOf, whole } from "./index";
import { type FluxState, INITIAL, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: FluxState): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLS10 closeId={CLOSE_IDS.august} initial={INITIAL[state]} />
    </QueryClientProvider>,
  );
}

async function ready(): Promise<void> {
  await waitFor(() => {
    expect(document.querySelectorAll("[data-line]").length).toBe(13);
  });
}

describe("CLS-10 Flux", () => {
  it("formats whole dollars and tenths as A6 says", () => {
    expect(whole("7670.00")).toBe("7,670");
    expect(whole("-1530.00")).toBe("(1,530)");
    expect(whole("0.00")).toBe("—");
    expect(whole(null)).toBe("—");
    expect(percent("-38.4")).toBe("(38.4%)");
    expect(percent("400.0")).toBe("400.0%");
  });

  it("a: only Payroll and Repairs are over both legs; Repairs is unexplained", async () => {
    expect(talliesOf(copperleafFluxAt("a"))).toEqual({
      tested: 13,
      over: 2,
      explained: 1,
      unexplained: 1,
      accepted: 0,
    });
    show("a");
    await ready();
    const over = [...document.querySelectorAll("[data-test='over_both']")].map((r) =>
      r.getAttribute("data-line"),
    );
    expect(over).toEqual(["payroll", "repairs_maintenance"]);
    expect(document.querySelectorAll("[data-variance='unexplained']").length).toBe(1);
    // S48 rest (DV-a, DV-b): code's subtotal rows in place, and the Adjustments count.
    const rows = [...document.querySelectorAll("tbody tr")].map(
      (r) => r.getAttribute("data-line") ?? `= ${r.getAttribute("data-subtotal") ?? ""}`,
    );
    expect(rows.indexOf("= gross_profit")).toBe(rows.indexOf("cogs") + 1);
    expect(rows.indexOf("= total_operating_expenses")).toBe(rows.indexOf("insurance") + 1);
    expect(rows.at(-1)).toBe("= net_income");
    const net = document.querySelector("[data-subtotal='net_income']");
    expect(net?.textContent).toContain("27,795");
    expect(net?.textContent).toContain("(3,660)");
    expect(screen.getByText("Explained · draft")).toBeTruthy();
    expect(screen.getByText("Threshold 10% and $2,500")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Accept" }).length).toBe(2);
  });

  it("raj: Accept is absent for a Senior", async () => {
    show("raj");
    await ready();
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Explain…" }).length).toBe(2);
  });

  it("b: both over lines explained after the client's answer", async () => {
    show("b");
    await ready();
    expect(screen.getAllByText("Explained").length).toBeGreaterThan(1);
    expect(document.querySelectorAll("[data-variance='unexplained']").length).toBe(0);
  });

  it("c: both accepted by Priya Raman raise the commentary banner", async () => {
    show("c");
    await ready();
    expect(screen.getAllByText("Accepted · PR").length).toBe(2);
    await waitFor(() => {
      expect(document.querySelector("[data-banner]")?.textContent).toBe(
        "2 accepted explanations will appear in the August commentary (CLS-08)",
      );
    });
  });

  it("d: year over year shows dashes and Not comparable, never a figure", async () => {
    show("d");
    await ready();
    expect(screen.getAllByText("Not comparable").length).toBe(13);
    const priors = [...document.querySelectorAll("[data-line] td:nth-child(2)")].map(
      (c) => c.textContent,
    );
    expect(new Set(priors)).toEqual(new Set(["—"]));
  });

  it("e: the agent tracing Repairs shows its spinner line", async () => {
    show("e");
    await ready();
    expect(
      document.querySelector("[data-line='repairs_maintenance'] [data-tracing]"),
    ).not.toBeNull();
  });
});
