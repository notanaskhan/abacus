// Q-05-T19 (TASK-8825): ADM-11 a–e at Tier C from scenarios. Row acceptance: "All six artboards
// render at Tier C from scenarios, ADM-11b reads 61 of 1,128 (5.4%) with 1 inspection and 2
// agent-monitoring findings, and axe reports no serious finding" (axe at the end pass).
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { ADM11, type ADM11Props } from "./index";
import { type Adm11ScenarioState, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});
let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Adm11ScenarioState, props: ADM11Props = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ADM11 {...props} />
    </QueryClientProvider>,
  );
}

describe("ADM-11 · Quality management dashboard", () => {
  it("a · six tiles, the totals and the override pane", async () => {
    show("a");
    // the tile and the agent row both read 6.0% (DEC-96: the firm rate and the agent's)
    expect((await screen.findAllByText("6.0%")).length).toBeGreaterThan(0);
    expect(screen.getByText("96.8%")).toBeTruthy();
    expect(screen.getByText(COPY.totalsAtRisk(2))).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelector("[data-adm11='override-total']")?.textContent).toContain(
        "3,410",
      );
    });
    expect(screen.getByText(COPY.unrated(9))).toBeTruthy();
  });

  it("b · Denver recomputes to 61 of 1,128 (5.4%) and objectives stay firm-wide", async () => {
    show("b", { office: "Denver" });
    expect(await screen.findByText("5.4%")).toBeTruthy();
    expect(screen.getByText(/61 of 1,128/u)).toBeTruthy();
    expect(screen.getByText(COPY.firmWide)).toBeTruthy();
  });

  it("c · the agent row expands to its reasons (37 = 21 + 9 + 7)", async () => {
    show("c", { expandedAgent: "ebp_audit_workpapers" });
    expect(
      await screen.findByText("Census column misread for rehired participants 21"),
    ).toBeTruthy();
    expect(screen.getByText(COPY.openFinding("QM-F-04"))).toBeTruthy();
    expect(screen.getByText(COPY.openLearned)).toBeTruthy();
  });

  it("d · before the first inspection: no findings and accuracy —", async () => {
    show("d");
    expect(await screen.findByText(COPY.emptyTitle)).toBeTruthy();
  });

  it("e · read-only for the Monitoring reviewer", async () => {
    show("e", { readOnly: true });
    await screen.findAllByText("6.0%");
    expect(document.querySelector("[data-screen='ADM-11']")?.getAttribute("data-readonly")).toBe(
      "true",
    );
  });
});
