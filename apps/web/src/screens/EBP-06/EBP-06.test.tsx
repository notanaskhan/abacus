// A-05-T40 (TASK-3321): EBP-06 in fixture mode. Row: "No amount is truncated, the TB and trust report
// list the same seven lines, and Sign off is disabled with the hold reason while points are open."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { EBP06_WORK_ITEM } from "../../fixtures/seed/ebp06";
import { newQueryClient } from "../../testing/support";
import { useInvestmentsCanvas } from "./Investments";
import { type Ebp06State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function Canvas({ layer }: { layer: "final" | "unadjusted" }): JSX.Element {
  const canvas = useInvestmentsCanvas(EBP06_WORK_ITEM, { layer });
  return (
    <div>
      <div data-test="actions">{canvas.actions}</div>
      {canvas.children}
    </div>
  );
}

function show(state: Ebp06State, layer: "final" | "unadjusted" = "final"): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Canvas layer={layer} />
    </QueryClientProvider>,
  );
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

describe("EBP-06", () => {
  it("a: figures are complete, and the certified lines read ✓ MS", async () => {
    show("a");
    const total = await drawn("[data-row='total']");
    expect(total.textContent).toContain("16,500,000.00");
    expect(total.textContent).toContain("13,940,000.00");
    expect((await drawn("[data-row='net_assets']")).textContent).toContain("16,861,000.00");
    const certified = document.querySelectorAll("[data-level='level1'], [data-level='nav']");
    expect(certified).toHaveLength(7);
    expect((await drawn("[data-row='krs_500']")).querySelector("[data-mark='ms']")).not.toBeNull();
  });

  it("a: notes receivable are a plain tick, never certified", async () => {
    show("a");
    const notes = await drawn("[data-row='notes']");
    expect(notes.querySelector("[data-mark='tick']")).not.toBeNull();
    expect(notes.querySelector("[data-mark='ms']")).toBeNull();
  });

  it("a: the level line foots", async () => {
    show("a");
    expect((await drawn("[data-ebp06='levels']")).textContent).toContain("16,500,000.00");
  });

  it("b: the Unadjusted layer reads 0.00 and 16,812,400", async () => {
    show("b", "unadjusted");
    expect((await drawn("[data-row='1200']")).textContent).toContain("0.00");
    expect((await drawn("[data-row='net_assets']")).textContent).toContain("16,812,400.00");
  });

  it("c: sign off is disabled with the hold reason while points are open", async () => {
    show("c");
    expect((await drawn("[data-ebp06='hold']")).textContent).toContain("Sign-off is held");
    const button = Array.from(document.querySelectorAll("button")).find((b) =>
      b.textContent.includes("Sign off"),
    );
    expect(button?.hasAttribute("disabled")).toBe(true);
  });

  it("a: a person's evaluated point has no Evaluate control", async () => {
    show("a");
    const point = await drawn("[data-point='period']");
    expect(point.dataset.answer).toBe("evaluated");
    expect(point.textContent).not.toContain("Evaluate");
  });
});
