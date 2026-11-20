// Q-05-T21 (TASK-8827): FIL-02 a–i. Row acceptance: "FIL-02a to i match at Tier C, Approve and
// destroy enables only when DESTROY 2026-Q3 is typed exactly, and Samuel Ito sees no write control."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { FIL02, type FIL02Props } from "./index";
import { type Fil02ScenarioState, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});
let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Fil02ScenarioState, props: FIL02Props = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(<QueryClientProvider client={newQueryClient()}><FIL02 {...props} /></QueryClientProvider>);
}

describe("FIL-02 · Retention & legal hold", () => {
  it("a · eight policies; audit documentation locked WORM", async () => {
    show("a");
    expect((await screen.findAllByText(/years$/u)).length).toBe(8);
    expect(screen.getByText(COPY.locked)).toBeTruthy();
    expect(screen.getByText(COPY.footer)).toBeTruthy();
  });
  it("b · two active holds", async () => {
    show("b", { tab: "holds" });
    expect((await screen.findAllByText(COPY.active)).length).toBe(2);
  });
  it("c · the batch waits for the second approval", async () => {
    show("c", { tab: "destruction" });
    expect(await screen.findByText(/Grace Holloway/u)).toBeTruthy();
    expect(screen.getByText(COPY.secondApproval)).toBeTruthy();
  });
  it("d · Approve and destroy enables only on the exact phrase", async () => {
    show("d", { tab: "destruction", initial: "approve" });
    const confirm = await screen.findByRole("button", { name: COPY.dialog.confirm });
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "destroy 2026-q3" } });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(input, { target: { value: "DESTROY 2026-Q3" } });
    expect((confirm as HTMLButtonElement).disabled).toBe(false);
  });
  it("e · held documents excluded: 1,201", async () => {
    show("e", { tab: "destruction" });
    expect(await screen.findByText(COPY.excluded(3, 1201))).toBeTruthy();
  });
  it("f · Samuel Ito sees no write control", async () => {
    show("f", { readOnly: true });
    await screen.findByText(COPY.footer);
    expect(screen.queryByRole("button", { name: COPY.newPolicy })).toBeNull();
    expect(screen.queryByRole("button", { name: COPY.approveBatch })).toBeNull();
  });
  it("g · the policy drawer lists every version", async () => {
    show("g", { initial: "drawer", drawerPolicyId: "00000000-0000-4000-8000-000000000001" });
    expect((await screen.findAllByText(/^v[12] · /u)).length).toBe(2);
  });
  it("h · Place hold, until released", async () => {
    show("h", { tab: "holds", initial: "hold" });
    expect(await screen.findByRole("switch", { name: COPY.holdSheet.until })).toBeTruthy();
  });
  it("i · destroyed with certificate DC-2026-Q3", async () => {
    show("i", { tab: "destruction" });
    expect(await screen.findByText(COPY.certificate("DC-2026-Q3"))).toBeTruthy();
  });
});
