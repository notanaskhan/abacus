// ADM-02 keyboard suite (G-01-T17; G-01 §9 item 4): the people table's row openers are buttons
// Tab reaches, each named for its person; the person drawer closes on Escape; the role menu opens
// on ArrowDown and closes on Escape with focus back on "Change role…"; switches say their state.
// axe runs in e2e/screens/adm-02.spec.ts (Playwright).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { nameOf, tabOrder } from "../../testing/keyboard";
import { newQueryClient } from "../../testing/support";
import { PeoplePage } from ".";
import { type Adm02State, OPENS, scenarios } from "./scenarios";

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

function show(state: Adm02State, initial: string = OPENS[state]): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <PeoplePage initial={initial} />
    </QueryClientProvider>,
  );
}

describe("ADM-02 keyboard (G-01 §9)", () => {
  it("each person row opens from a named button Tab reaches", async () => {
    show("a", "?q=osei");
    const open = await screen.findByRole("button", { name: "Open Kevin Osei" });
    expect(tabOrder()).toContain(open);
    expect(tabOrder().filter((el) => nameOf(el) === "")).toEqual([]);
  });

  it("the role menu opens on ArrowDown and Escape gives focus back to Change role…", async () => {
    show("a", "?q=osei");
    fireEvent.click(await screen.findByRole("button", { name: "Open Kevin Osei" }));
    const dialog = await screen.findByRole("dialog", { name: "Kevin Osei" });
    const trigger = await within(dialog).findByRole("button", { name: "Change role…" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const senior = await screen.findByRole("menuitemradio", { name: "Senior" });
    fireEvent.keyDown(senior, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("menuitemradio", { name: "Senior" })).toBeNull();
    });
    expect(document.activeElement).toBe(trigger);
  });

  it("the person drawer closes on Escape", async () => {
    show("d");
    const dialog = await screen.findByRole("dialog", { name: "Lena Park" });
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Lena Park" })).toBeNull();
    });
  });

  it("the offshore control is a switch that says its state", async () => {
    show("d");
    const dialog = await screen.findByRole("dialog", { name: "Lena Park" });
    const offshore = await within(dialog).findByRole("switch", { name: "Offshore / restricted" });
    expect(offshore.getAttribute("aria-checked")).toBe("false");
    expect(tabOrder(dialog)).toContain(offshore);
  });
});
