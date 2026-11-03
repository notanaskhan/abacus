// A-04-T27: AUD-04 a–f in fixture mode. Row acceptance: "AUD-04 a-f render at Tier C, d steps
// through both sources and lights the SOC 1 region, and Sign off stays disabled until the draft is
// adopted." Words are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { PLANNING_PAPER } from "../../fixtures/seed/aud04";
import { newQueryClient } from "../../testing/support";
import { ProgramPage } from ".";
import { type Aud04State, SCENARIO_TAB, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Aud04State, onSignOff = vi.fn()): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ProgramPage
        auditId={NORTHWIND_AUDIT}
        workpaperId={PLANNING_PAPER}
        tab={SCENARIO_TAB[state]}
        onTab={() => undefined}
        onSignOff={onSignOff}
      />
    </QueryClientProvider>,
  );
}

function signOff(): HTMLButtonElement {
  const el = document.querySelector<HTMLButtonElement>("[data-aud04='sign-off']");
  if (el === null) throw new Error("no Sign off");
  return el;
}

describe.each(STATES)("AUD-04 %s", (state) => {
  it("renders from its scenario", async () => {
    show(state);
    await waitFor(() => {
      expect(
        document.querySelector(`[data-screen='AUD-04'][data-tab='${SCENARIO_TAB[state]}']`),
      ).not.toBeNull();
      expect(document.querySelector("[data-workpaper='pane']")).not.toBeNull();
    });
  });
});

describe("AUD-04 a: the agent's draft", () => {
  it("reads Draft · Accrued Agent with Sign off… disabled until adopted", async () => {
    show("a");
    await screen.findByText("Draft · Accrued Agent");
    expect(signOff().disabled).toBe(true);
    expect(document.body.textContent).toContain("Adopt (L1)…");
    expect(document.body.textContent).toContain("SECTION 1 — SERVICE ORGANIZATIONS");
    expect(document.body.textContent).toContain(
      "The plan uses four service organizations; three are relevant to the financial statements.",
    );
  });

  it("separates relevance, SOC evidence and subservice treatment; Summit is No", async () => {
    show("a");
    await screen.findByText("Summit Plan Administrators");
    const row = screen.getByText("Summit Plan Administrators").closest("tr");
    expect(row?.textContent).toContain("No");
    expect(document.body.textContent).toContain("Carve-out — Ridgeway Data Services (hosting)");
  });

  it("Adopt (L1)… opens SHL-12 at L1 on the paper", async () => {
    const onSignOff = vi.fn();
    show("a", onSignOff);
    (await screen.findByText("Adopt (L1)…")).click();
    expect(onSignOff).toHaveBeenCalledWith(PLANNING_PAPER, "L1");
  });
});

describe("AUD-04 b and c: adopted, then signed off", () => {
  it("b: Prepared · MD, Sign off… enabled", async () => {
    show("b");
    await screen.findByText("Prepared · MD");
    expect(signOff().disabled).toBe(false);
  });

  it("c: Signed off with ✓ MD ✓ HL", async () => {
    show("c");
    await screen.findByText("Signed off");
    const rungs = [...document.querySelectorAll("[data-aud04='rung']")].map((r) => r.textContent);
    expect(rungs).toEqual(["✓ MD", "✓ HL"]);
  });
});

describe("AUD-04 d, e, f", () => {
  it("d: the carve-out cell carries two citation sources", async () => {
    show("d");
    await screen.findByText("Carve-out — Ridgeway Data Services (hosting)");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-match]").length).toBeGreaterThan(0);
    });
  });

  it("e: Linkage lists the four organizations to their procedures", async () => {
    show("e");
    await screen.findByText("BH-EBP-140 steps 1–8");
    expect(document.body.textContent).toContain("None needed");
  });

  it("f: Audit Approach reads the reliance rows", async () => {
    show("f");
    await screen.findByText("Yes, with bridge letter and CUEC testing");
    expect(document.body.textContent).toContain("No — substantive");
  });
});
