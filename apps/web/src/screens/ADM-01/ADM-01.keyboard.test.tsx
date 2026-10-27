// ADM-01 keyboard suite (G-01-T17; G-01 §9 item 4): the firm profile is reachable by Tab in
// reading order with every control named; a menu opens on ArrowDown and closes on Escape with
// focus back on its trigger; Save is out of the Tab order until the form is dirty. axe runs in
// e2e/screens/adm-01.spec.ts (Playwright).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { nameOf, tabOrder } from "../../testing/keyboard";
import { newQueryClient } from "../../testing/support";
import { ADM01 } from ".";
import { type Adm01State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

function show(state: Adm01State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ADM01 onNavigate={vi.fn()} />
    </QueryClientProvider>,
  );
}

const ZONE = "Default time zone: Central Time (CT)";

describe("ADM-01 keyboard (G-01 §9)", () => {
  it("every control Tab reaches has a name", async () => {
    show("a");
    await screen.findByRole("button", { name: ZONE });
    const order = tabOrder();
    expect(order.length).toBeGreaterThan(3);
    expect(order.filter((el) => nameOf(el) === "")).toEqual([]);
  });

  it("the time-zone menu opens on ArrowDown and Escape gives focus back to it", async () => {
    show("b");
    const zone = await screen.findByRole("button", { name: ZONE });
    zone.focus();
    fireEvent.keyDown(zone, { key: "ArrowDown" });
    const item = await screen.findByRole("menuitemradio", { name: "Eastern Time (ET)" });
    fireEvent.keyDown(item, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("menuitemradio", { name: "Eastern Time (ET)" })).toBeNull();
    });
    expect(document.activeElement).toBe(zone);
  });

  it("Save leaves the Tab order while the form is clean", async () => {
    show("a");
    await screen.findByRole("button", { name: ZONE });
    expect(tabOrder().some((el) => nameOf(el) === "Save")).toBe(false);
  });
});
