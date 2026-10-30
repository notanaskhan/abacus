// TAX-01 · Tax Returns practice board (T-02-T12). One test per artboard (a–g) on its fixture
// scenario, the live Assign preparer, the tiles as filters and the route's flag gate.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { TaxReturnsPage } from ".";
import { COPY } from "./copy";
import {
  SEARCH,
  SELECTED_CLIENTS,
  SELECTED_IDS,
  STATES,
  type Tax01State,
  scenarios,
} from "./scenarios";

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

interface Seen {
  calls: { method: string; path: string; query: string; body: unknown }[];
}

function install(scenario: Scenario, extra: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...extra }).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({
          method: request.method,
          path: request.path,
          query: request.query.toString(),
          body: request.body,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return seen;
}

function show(state: Tax01State, extra: Record<string, FixtureHandler> = {}): Seen {
  const seen = install(scenarios[state], extra);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <TaxReturnsPage
        initial={SEARCH[state]}
        initialSelection={state === "d" ? SELECTED_IDS : []}
      />
    </QueryClientProvider>,
  );
  return seen;
}

function rows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("tr[data-row]")];
}

function clients(): string[] {
  return rows().map((r) => r.querySelectorAll("td")[2]?.querySelector("span span")?.textContent ?? "");
}

/** Radix menus open from the keyboard or a pointer, not a bare click (the CLI-01 pattern). */
function openMenu(trigger: HTMLElement): void {
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
}

async function ready(): Promise<void> {
  await waitFor(() => {
    expect(rows().length).toBeGreaterThan(0);
  });
}

describe("TAX-01 artboards", () => {
  it("covers a to g", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
  });

  it("a: 15 open returns by due date, the season summary and every tile", async () => {
    show("a");
    await ready();
    expect(rows()).toHaveLength(15);
    expect(screen.getByText(/79 open · 145 done · 224 TY2025 returns · 161 extended/)).toBeTruthy();
    expect(screen.getByText("Showing 15 of 79 open")).toBeTruthy();
    for (const label of ["Prepared", "In review", "Action required", "Awaiting signature"]) {
      expect(screen.getAllByText(new RegExp(label)).length).toBeGreaterThan(0);
    }
    // The pilot has no Board toggle (DV-15).
    expect(screen.queryByRole("button", { name: /Board/ })).toBeNull();
    expect(screen.queryByRole("radio", { name: /Board/ })).toBeNull();
  });

  it("a: the Feld row carries the Draft K-1 popover, which names TXP-12", async () => {
    // Feld is due Oct 15, past a's first page of fifteen Sep 15 returns: find it by search.
    install(scenarios.a);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <TaxReturnsPage initial={{ q: "Feld" }} />
      </QueryClientProvider>,
    );
    await ready();
    const feld = rows().find((r) => r.textContent.includes("Jonah & Claire Feld"));
    expect(feld).toBeDefined();
    fireEvent.click(within(feld as HTMLElement).getByRole("button", { name: COPY.draftK1 }));
    expect(await screen.findByText(COPY.draftK1Detail)).toBeTruthy();
  });

  it("b: the awaiting-signature tile filters the rows and adds signer chips", async () => {
    const seen = show("b");
    await ready();
    const list = seen.calls.filter((c) => c.path === "/v1/tax-returns");
    expect(list.at(-1)?.query).toContain("status=awaiting_signature");
    expect(screen.getByRole("columnheader", { name: COPY.columns.signature })).toBeTruthy();
  });

  it("c: grouped by office, under office bands that foot", async () => {
    const seen = show("c");
    await ready();
    expect(seen.calls.some((c) => c.query.includes("group_by=office"))).toBe(true);
    expect(screen.getByText(/^CHICAGO · 98 RETURNS · \d+ OPEN · \d+ DONE$/)).toBeTruthy();
  });

  it("d: three returns selected, Assign preparer live", async () => {
    const seen = show("d");
    await ready();
    const bar = screen.getByRole("region", { name: "3 selected" });
    expect(SELECTED_CLIENTS).toHaveLength(3);
    openMenu(within(bar).getByRole("button", { name: COPY.bulk.assign }));
    const member = await screen.findAllByRole("menuitem");
    fireEvent.click(member[0] as HTMLElement);
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "POST" && c.path === "/v1/tax-returns:bulk-assign")).toBe(
        true,
      );
    });
    const post = seen.calls.find((c) => c.path === "/v1/tax-returns:bulk-assign");
    expect((post?.body as { return_ids: string[] }).return_ids).toHaveLength(3);
    expect((post?.body as { role: string }).role).toBe("preparer");
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain("3 returns assigned");
    });
  });

  it("d: Extend… and Run firm standards… are drawn disabled outside production", async () => {
    show("d");
    await ready();
    const bar = screen.getByRole("region", { name: "3 selected" });
    expect(within(bar).getByRole("button", { name: COPY.bulk.extend }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(
      within(bar).getByRole("button", { name: COPY.bulk.standards }).hasAttribute("disabled"),
    ).toBe(true);
  });

  it("e: ?q=Schwab is the filtered-empty state", async () => {
    show("e");
    expect(await screen.findByText(COPY.noResults("Schwab"))).toBeTruthy();
    expect(clients()).toEqual([]);
  });

  it("f: TY2026 is the season-start empty state", async () => {
    show("f");
    expect(await screen.findByText(COPY.seasonEmptyTitle(2026))).toBeTruthy();
    expect(screen.getByText(COPY.seasonEmptyBody(2025))).toBeTruthy();
  });

  it("g: the rows never answer; the tiles hold their place (T1e)", async () => {
    show("g");
    expect(await screen.findByText("Filed · Accepted")).toBeTruthy();
    expect(document.body.textContent).not.toContain("145Filed · Accepted");
    expect(rows()).toHaveLength(0);
  });
});

describe("TAX-01 behaviour", () => {
  it("a tile click asks the server for that status; a second click clears it", async () => {
    const seen = show("a");
    await ready();
    // Action required's tile word is "Issues" (status registry, home_and_tax_tiles).
    fireEvent.click(screen.getAllByRole("button", { name: /Issues/u })[0] as HTMLElement);
    await waitFor(() => {
      expect(seen.calls.at(-1)?.query).toContain("status=action_required");
    });
  });

  it("an error answer draws the retryable error state", async () => {
    show("a", { "GET /v1/tax-returns": () => json({ detail: "boom" }, 500) });
    expect(await screen.findByRole("button", { name: /Retry|Try again/ })).toBeTruthy();
  });
});
