// BND-01 keyboard suite (P-06-T26; P-06 §5.6): Tab reaches the filters, the tiles, search and the
// pane's primary actions in reading order; the tiles are toggle buttons with aria-pressed; every
// overlay the screen opens (row menu, Unpublish dialog, New binder sheet, follow-up sheet) closes
// on Escape and gives focus back to the control that opened it. axe runs in
// e2e/screens/BND-01.spec.ts (Playwright).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { type BinderFilters, defaultBinderFilters } from "../../domain/requests";
import { positions, tabOrder } from "../../testing/keyboard";
import { newQueryClient } from "../../testing/support";
import { BND01 } from ".";
import { type Bnd01State, SEARCH, SELECTED, scenarios } from "./scenarios";

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

function Harness({
  initial,
  selected,
}: {
  initial: BinderFilters;
  selected: string | null;
}): JSX.Element {
  const [filters, setFilters] = useState(initial);
  return <BND01 filters={filters} onFilters={setFilters} initialSelected={selected} />;
}

async function show(state: Bnd01State): Promise<void> {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Harness
        initial={{ ...defaultBinderFilters("2026-09-14"), ...SEARCH[state] }}
        selected={SELECTED[state] ?? null}
      />
    </QueryClientProvider>,
  );
  await screen.findByText(/^Showing /);
}

function rowOf(client: string): HTMLElement {
  const row = [...document.querySelectorAll<HTMLElement>("tr[data-row]")].find(
    (r) => within(r).queryByText(client, { exact: true }) !== null,
  );
  if (row === undefined) throw new Error(`no row for ${client}`);
  return row;
}

/** Focus a control and activate it, as Enter or Space on a focused button does. */
function press(el: HTMLElement): void {
  el.focus();
  fireEvent.click(el);
}

async function closesOnEscape(dialog: HTMLElement, opener: HTMLElement): Promise<void> {
  fireEvent.keyDown(dialog, { key: "Escape" });
  await waitFor(() => {
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  await waitFor(() => {
    expect(document.activeElement).toBe(opener);
  });
}

describe("BND-01 keyboard (P-06 §5.6)", () => {
  it("Tab reaches the filters, then the tiles, search, the pane actions and the rows, in order", async () => {
    await show("a");
    const at = positions(document.body, [
      "Service: Tax returns",
      "Client activity: Any",
      // A tile reads its count, then its label ("1Draft").
      /Draft$/,
      /Closed$/,
      "Search binders",
      "Send reminders…",
      "New binder…",
      /actions$/,
    ]);
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((x, y) => x - y)).toEqual(at);
    // No positive tabindex anywhere: document order is the tab order.
    expect(tabOrder().filter((el) => el.tabIndex > 0)).toEqual([]);
  });

  it("the tiles are toggle buttons with aria-pressed", async () => {
    await show("a");
    const group = screen.getByRole("group", { name: "Status" });
    const complete = within(group).getByRole("button", { name: /Complete/ });
    expect(complete.getAttribute("aria-pressed")).toBe("false");
    press(complete);
    expect(await screen.findByText("Showing 4 of 40")).toBeTruthy();
    expect(
      within(screen.getByRole("group", { name: "Status" }))
        .getByRole("button", { name: /Complete/ })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("the row menu opens from the keyboard and Escape gives focus back to its trigger", async () => {
    await show("a");
    const trigger = within(rowOf("Jonah & Claire Feld")).getByRole("button", { name: /actions$/ });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const menu = await screen.findByRole("menu");
    fireEvent.keyDown(menu, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("menu")).toBeNull();
    });
    expect(document.activeElement).toBe(trigger);
  });

  it("Unpublish…: Escape closes the reason dialog and focus returns to the row's actions", async () => {
    await show("a");
    const trigger = within(rowOf("Gloria Mendez")).getByRole("button", { name: /actions$/ });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const menu = await screen.findByRole("menu");
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Unpublish…" }));
    const dialog = await screen.findByRole("dialog", { name: "Unpublish binder" });
    await closesOnEscape(dialog, trigger);
  });

  it("New binder…: Escape closes the sheet and focus returns to New binder…", async () => {
    await show("a");
    const opener = await screen.findByRole("button", { name: "New binder…" });
    press(opener);
    const sheet = await screen.findByRole("dialog", { name: "New binder" });
    await closesOnEscape(sheet, opener);
  });

  it("Send reminder…: Escape closes the follow-up sheet, nothing is sent, focus returns", async () => {
    const sent: string[] = [];
    restore = installFixtureMode({
      ...scenarios.b,
      handlers: {
        ...scenarios.b.handlers,
        "POST /v1/follow-ups/send": (request) => {
          sent.push(request.path);
          return scenarios.b.handlers["POST /v1/follow-ups/send"]?.(request) ?? new Response();
        },
      },
    });
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Harness
          initial={{ ...defaultBinderFilters("2026-09-14"), ...SEARCH.b }}
          selected={SELECTED.b ?? null}
        />
      </QueryClientProvider>,
    );
    const opener = await screen.findByRole("button", { name: "Send reminder…" });
    press(opener);
    const sheet = await screen.findByRole("dialog", { name: "Send follow-ups · 1" });
    await within(sheet).findByText("Nothing is sent until you click Send.");
    await closesOnEscape(sheet, opener);
    expect(sent).toEqual([]);
  });
});
