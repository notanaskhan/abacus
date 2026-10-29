// SIG-01 · Signatures hub (N-02-T11; DEC-827). Acceptance (the task row): "Scenario tests for a, b,
// c, d, e and g pass at 1400 with the DF-11 copy in the E2 drawer and no Send new link at unlock."
import { client } from "@abacus/api-client/client";
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { SIG01 } from ".";
import { COPY } from "./copy";
import { OPENS, type Sig01State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function mount(state: Sig01State): void {
  restore = installFixtureMode(scenarios[state]);
  const open = OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () => <SIG01 initialTab={open.tab} initialEnvelope={open.envelope} />,
    },
  ]);
}

describe("SIG-01", () => {
  it("a: out for signature with the E2 drawer and the DF-11 copy, no Send new link", async () => {
    mount("a");
    expect(await screen.findAllByText(/Thomas & Irene Kowal/)).not.toHaveLength(0);
    const drawer = await screen.findByRole("dialog");
    expect(within(drawer).getByText(COPY.df11.needsHandwritten)).toBeTruthy();
    expect(within(drawer).getByRole("button", { name: COPY.df11.upload })).toBeTruthy();
    expect(within(drawer).queryByText(/Send new link at unlock/)).toBeNull();
  });

  it("a: the tiles foot 8, 5, 4 and 4", async () => {
    mount("a");
    await screen.findAllByText(/Thomas & Irene Kowal/);
    for (const label of [COPY.tiles.sent, COPY.tiles.viewed, COPY.tiles.partiallySigned]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(COPY.summary)).toBeTruthy();
  });

  it("b: two drafts to send, the agent's drafted via Agent", async () => {
    mount("b");
    expect(await screen.findByText(/Harborview Dental Properties, LP/)).toBeTruthy();
    expect(screen.getByText(/Form 2848 · Aurelio Santos/)).toBeTruthy();
  });

  it("c: completed, last 30 days", async () => {
    mount("c");
    expect(await screen.findByText(/Summit Line Logistics, Inc\./)).toBeTruthy();
  });

  it("d: the expired consent", async () => {
    mount("d");
    expect(await screen.findByText(/disclosure to offshore preparers/)).toBeTruthy();
  });

  it("e: the declined variant", async () => {
    mount("e");
    expect(await screen.findByText(/Noor & Adam Farouk/)).toBeTruthy();
    expect(screen.getAllByText("Declined").length).toBeGreaterThan(0);
  });

  it("g: empty To send", async () => {
    mount("g");
    expect(await screen.findByText(COPY.empty.title)).toBeTruthy();
  });
});
