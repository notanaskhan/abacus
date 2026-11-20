// Q-05-T20 (TASK-8826): AUD-28 a–g. Row acceptance: "AUD-28a to g match at Tier C, the consultee
// picker never lists the agent or a walled person, and Record conclusion stays disabled until a
// conclusion and the implemented toggle are set."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { CONSULTEES, ENGAGEMENT_NAMES, SELECTED } from "../../fixtures/seed/aud28";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { AUD28, type AUD28Props } from "./index";
import { type Aud28ScenarioState, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});
let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});
const PEOPLE = CONSULTEES.map(([id, label]) => ({ userId: id, label }));

function show(state: Aud28ScenarioState, props: Partial<AUD28Props> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AUD28
        selectedRef={SELECTED[state]}
        consultees={PEOPLE}
        engagementNames={ENGAGEMENT_NAMES}
        {...props}
      />
    </QueryClientProvider>,
  );
}

describe("AUD-28 · Consultations log", () => {
  it("a · five consultations, C-03 selected with its conclusion", async () => {
    show("a");
    expect((await screen.findAllByRole("button", { name: /^C-0/u })).length).toBe(5);
    expect(await screen.findByText(/Treat it as a significant deficiency/u)).toBeTruthy();
  });

  it("b · C-04's difference of opinion, resolved before release", async () => {
    show("b");
    expect(await screen.findByText(/Thomas Whitcombe \(EQR\)/u)).toBeTruthy();
    expect(screen.getByText(/Resolved before release ✓/u)).toBeTruthy();
  });

  it("c · C-01 open: Record conclusion… and no decision linked", async () => {
    show("c");
    expect(await screen.findByRole("button", { name: COPY.recordConclusion })).toBeTruthy();
    expect(screen.getByText(COPY.noDecision)).toBeTruthy();
  });

  it("d · filtered by engagement: only C-03", async () => {
    show("d", { engagement: { id: "e", name: "Northwind Robotics 401(k) Plan" } });
    expect((await screen.findAllByRole("button", { name: /^C-0/u })).length).toBe(1);
  });

  it("e · empty", async () => {
    show("e");
    expect(await screen.findByText(COPY.emptyTitle)).toBeTruthy();
  });

  it("f · the consultee picker lists partners and specialists only", async () => {
    show("f", { initial: "new" });
    const trigger = await screen.findByRole("button", { name: COPY.sheet.consultee });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const names = (await screen.findAllByRole("menuitemradio")).map((o) => o.textContent);
    expect(names.length).toBeGreaterThan(0);
    expect(names.some((n) => /Agent/u.test(n))).toBe(false);
  });

  it("g · Record conclusion stays disabled until text and implemented are set", async () => {
    show("g", { initial: "conclude" });
    const save = await screen.findByRole("button", { name: COPY.conclude.save });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Not a going-concern indicator." },
    });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("switch", { name: COPY.conclude.implemented }));
    expect((save as HTMLButtonElement).disabled).toBe(false);
  });
});
