// A-05-T52 (TASK-6114): EBP-08 in fixture mode. Rows crossfoot and the Total foots to 16,812,400;
// the BrokerWindow types tie to 1,605,000; the six 2025 terminations are fully vested; the running
// state shows skeleton rows and the running pill; off shows the flag-off state.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { EBP08_WORK_ITEM } from "../../fixtures/seed/ebp08";
import { newQueryClient } from "../../testing/support";
import { useAccountsCanvas } from "./Accounts";
import { COPY } from "./copy";
import { type Ebp08State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

type Tab = "rollforward" | "brokerwindow" | "vesting";

function Canvas({ tab, running }: { tab: Tab; running: boolean }): JSX.Element {
  const canvas = useAccountsCanvas(EBP08_WORK_ITEM, { tab, running });
  return <div>{canvas.children}</div>;
}

function show(state: Ebp08State, tab: Tab = "rollforward", running = false): HTMLElement {
  restore = installFixtureMode(scenarios[state]);
  return render(
    <QueryClientProvider client={newQueryClient()}>
      <Canvas tab={tab} running={running} />
    </QueryClientProvider>,
  ).container;
}

describe("EBP-08 participant accounts", () => {
  it("d: the statement foots to 16,812,400 and every tie shows Ties", async () => {
    const root = show("d");
    await waitFor(() => {
      expect(root.querySelector('[data-group="total"]')).not.toBeNull();
    });
    const total = root.querySelector('[data-group="total"]');
    expect(total?.textContent).toContain("16,812,400");
    expect(total?.textContent).toContain("14,228,500");
    expect(root.querySelector('[data-group="active"]')?.textContent).toContain("(871,900)");
    expect(
      root.querySelectorAll('[data-tie="contributions_allocated"], [data-tie="fees"]').length,
    ).toBe(2);
    expect(screen.getAllByText(COPY.tally.ties).length).toBeGreaterThanOrEqual(4);
    expect(root.textContent).not.toContain("$");
  });

  it("a: running shows skeleton rows, Pending tallies and the running pill", async () => {
    const root = show("a", "rollforward", true);
    await waitFor(() => {
      expect(root.querySelector('[data-ebp08="running"]')).not.toBeNull();
    });
    expect(root.querySelectorAll("[data-skeleton]").length).toBe(3);
    expect(screen.getAllByText(COPY.tally.pending).length).toBe(5);
    expect(screen.getByText(COPY.running)).toBeTruthy();
  });

  it("b: the brokerage types tie to 1,605,000", async () => {
    const root = show("b", "brokerwindow");
    await waitFor(() => {
      expect(root.querySelector('[data-security="total"]')).not.toBeNull();
    });
    expect(root.querySelector('[data-security="total"]')?.textContent).toContain("1,605,000");
    expect(root.querySelectorAll("[data-security]").length).toBe(4);
  });

  it("c: six fully vested 2025 terminations and no forfeitures", async () => {
    const root = show("c", "vesting");
    await waitFor(() => {
      expect(root.querySelector('[data-ebp08="forfeitures"]')).not.toBeNull();
    });
    expect(root.querySelectorAll("[data-participant]").length).toBe(6);
    expect(screen.getByText(COPY.participants(6))).toBeTruthy();
    expect(screen.getAllByText(COPY.agrees).length).toBe(6);
  });

  it("off: the flag-off state, no statement", async () => {
    const root = show("off");
    await waitFor(() => {
      expect(root.querySelector('[data-ebp08="off"]')).not.toBeNull();
    });
    expect(root.querySelector('[data-ebp08="statement"]')).toBeNull();
  });
});
