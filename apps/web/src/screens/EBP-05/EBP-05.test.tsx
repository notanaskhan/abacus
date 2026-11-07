// A-05-T44 (TASK-5124): EBP-05 in fixture mode. Row: "Offsets are labelled distributions on line
// 2e(1) everywhere and never 'deemed distributions'."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { EBP05_WORK_ITEM } from "../../fixtures/seed/ebp05";
import { newQueryClient } from "../../testing/support";
import { useLoansCanvas } from "./Loans";
import { type Ebp05State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function Canvas({ tab }: { tab: "loans" | "distributions" }): JSX.Element {
  const canvas = useLoansCanvas(EBP05_WORK_ITEM, { tab });
  return (
    <div>
      <div data-test="actions">{canvas.actions}</div>
      {canvas.children}
    </div>
  );
}

function show(state: Ebp05State, tab: "loans" | "distributions" = "loans"): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Canvas tab={tab} />
    </QueryClientProvider>,
  );
}

describe("EBP-05", () => {
  it("a: the rollforward foots and offsets are benefits paid on line 2e(1)", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelector('[data-card="rollforward"]')).not.toBeNull();
    });
    const text = document.body.textContent;
    expect(text).toContain("$312,400.00");
    expect(text).toContain("(Schedule H line 2e(1))");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-offset]")).toHaveLength(3);
    });
  });

  it("never calls an offset a deemed distribution", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelector('[data-card="offsets"]')).not.toBeNull();
    });
    const card = document.querySelector('[data-card="offsets"]')?.textContent ?? "";
    const rows = [...document.querySelectorAll("[data-offset]")].map((r) => r.textContent);
    for (const row of rows) expect(row.toLowerCase()).not.toContain("deemed");
    expect(card).toContain("no §72(p) deemed distributions");
    expect(document.querySelector('[data-tally="deemed"]')?.textContent).toContain("$0.00");
  });

  it("agent ticks stay outlined before adoption", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelector('[data-tick="agent"]')).not.toBeNull();
    });
    expect(document.querySelector('[data-tick="adopted"]')).toBeNull();
  });

  it("b: the distributions tab shows the sample against its population", async () => {
    show("b", "distributions");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-distribution]")).toHaveLength(10);
    });
    expect(document.querySelector('[data-tally="sample"]')?.textContent).toContain("10 of 64");
  });

  it("c: a comparative that doesn't agree offers Raise exception", async () => {
    show("c");
    await waitFor(() => {
      expect(document.querySelector("[data-comparative]")).not.toBeNull();
    });
    expect(document.querySelector("[data-exception]")?.textContent).toContain("Raise exception");
  });

  it("no new loan exceeds its limit in the seed", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-loan]")).toHaveLength(5);
    });
    expect(document.querySelector('[data-card="new-loans"]')?.textContent).toContain("$96,200.00");
  });
});
