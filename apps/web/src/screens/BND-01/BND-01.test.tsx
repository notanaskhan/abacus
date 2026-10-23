// BND-01 · Binders index (P-06-T09). One test per artboard this task builds (a, c, d, e) on its
// fixture scenario, the spec's acceptance checklist, the error and filtered-empty states, the tiles
// filtering the rows, and the row ··· menu and "New binder…" sheet against the C5 routes.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { type BinderFilters, defaultBinderFilters } from "../../domain/requests";
import { BINDER_COUNTS, BINDER_PARTS } from "../../fixtures/seed/binders";
import { bindersRoute } from "../../routes/firm/binders";
import { newQueryClient } from "../../testing/support";
import { BND01 } from ".";
import { type Bnd01State, SEARCH, STATES, scenarios } from "./scenarios";

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

function install(scenario: Scenario): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
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

function Harness({ initial }: { initial: BinderFilters }): JSX.Element {
  const [filters, setFilters] = useState(initial);
  return <BND01 filters={filters} onFilters={setFilters} />;
}

function show(state: Bnd01State, scenario: Scenario = scenarios[state]): Seen {
  const seen = install(scenario);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Harness initial={{ ...defaultBinderFilters("2026-09-14"), ...SEARCH[state] }} />
    </QueryClientProvider>,
  );
  return seen;
}

async function rows(): Promise<HTMLElement[]> {
  await screen.findByText(/^Showing /);
  return [...document.querySelectorAll<HTMLElement>("tr[data-row]")];
}

function rowOf(client: string, binder = "2025 Binder"): HTMLElement {
  const row = [...document.querySelectorAll<HTMLElement>("tr[data-row]")].find(
    (r) =>
      r.querySelector("td")?.textContent === binder &&
      within(r).queryByText(client, { exact: true }) !== null,
  );
  if (row === undefined) throw new Error(`no row for ${binder} · ${client}`);
  return row;
}

function tiles(): Record<string, string> {
  const group = screen.getByRole("group", { name: "Status" });
  return Object.fromEntries(
    within(group)
      .getAllByRole("button")
      .map((b) => [b.dataset.tile ?? "", b.querySelector("span")?.textContent ?? ""]),
  );
}

function statusOf(row: HTMLElement): string {
  return row.querySelectorAll("td")[4]?.textContent ?? "";
}

function cell(row: HTMLElement, index: number): string {
  return row.querySelectorAll("td")[index]?.textContent ?? "";
}

function openMenu(row: HTMLElement): HTMLElement {
  const trigger = within(row).getByRole("button", { name: /actions$/ });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  return screen.getByRole("menu");
}

describe("BND-01 artboards", () => {
  it("defines exactly the artboards P-06-T09 builds", () => {
    expect(STATES).toEqual(["a", "c", "d", "e"]);
    for (const s of STATES) expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    expect(scenarios.a.persona).toBe("grace-holloway");
    expect(scenarios.c.persona).toBe("remy-vidal");
  });

  it("BND-01a default", async () => {
    show("a");
    const list = await rows();
    expect(list).toHaveLength(15);
    expect(screen.getByText("Showing 15 of 241")).toBeTruthy();
    expect(tiles()).toEqual({
      Draft: "1",
      Published: "48",
      Unpublished: "0",
      Complete: "40",
      Closed: "152",
    });
    expect(
      screen.getByText("241 TY2025 binders · 224 returns · 17 second-part binders"),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Service: Tax returns" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Season: TY2025" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Office: All offices" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Preparer: All" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Client activity: Any" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Binders" })).toBeTruthy();
    const feld = rowOf("Jonah & Claire Feld");
    expect(cell(feld, 2)).toBe("2025 Form 1040");
    expect(cell(feld, 3)).toContain("5 of 7");
    expect(statusOf(feld)).toBe("Published");
    expect(cell(feld, 6)).toBe("KO");
    expect(cell(rowOf("Ridgeline Property Partners, LP", "2025 Binder pt 2"), 3)).toContain(
      "1 of 3",
    );
  });

  it("BND-01c unpublished row", async () => {
    show("c");
    const list = await rows();
    expect(list).toHaveLength(16);
    expect(screen.getByText("Showing 16 of 241")).toBeTruthy();
    expect(tiles()).toEqual({
      Draft: "1",
      Published: "47",
      Unpublished: "1",
      Complete: "40",
      Closed: "152",
    });
    const osterberg = rowOf("Benjamin Osterberg");
    expect(statusOf(osterberg)).toBe(
      "UnpublishedUnpublished Sep 2 by Remy Vidal — fixing 2 requests",
    );
    expect(cell(osterberg, 3)).toContain("0 of 9");
    expect(cell(osterberg, 5)).toBe("—");
    expect(cell(osterberg, 6)).toBe("RV");
    // It sits after Quintero: newest client activity within each state, neither has any.
    const order = list.map((r) => cell(r, 1));
    expect(order.indexOf("Benjamin Osterberg")).toBe(order.indexOf("Rafael Quintero") + 1);
  });

  it("BND-01d season empty", async () => {
    show("d");
    expect(await screen.findByText("No TY2026 binders yet.")).toBeTruthy();
    expect(
      screen.getByText("Season setup creates binders from each client's TY2025 return."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open season setup" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Season: TY2026" })).toBeTruthy();
    // T1c: no tiles, no count.
    expect(screen.queryByRole("group", { name: "Status" })).toBeNull();
    expect(screen.queryByText(/^Showing /)).toBeNull();
    expect(document.querySelectorAll("tr[data-row]")).toHaveLength(0);
  });

  it("BND-01e loading", async () => {
    show("e");
    const busy = await screen.findByRole("status", { name: "Loading" }, { timeout: 2000 });
    expect(busy.getAttribute("aria-busy")).toBe("true");
    await waitFor(() => {
      expect(busy.children.length).toBe(8);
    });
    // The real header and column heads stay; a tile never reads a count it does not have.
    expect(screen.getByRole("heading", { name: "Binders" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Last client activity" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Status" })).toBeNull();
  });

  it("error: a 5xx shows the error frame with Retry", async () => {
    const failing: Scenario = {
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        "GET /v1/binders": () => json({ detail: "unavailable" }, 503),
      },
    };
    show("a", failing);
    expect(await screen.findByText("Couldn’t load binders.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
  });
});

describe("BND-01 acceptance (spec.md checklist)", () => {
  it("BND-01 acceptance: tiles foot to 241 (1 + 48 + 0 + 40 + 152)", async () => {
    show("a");
    await rows();
    const sum = Object.values(tiles()).reduce((n, v) => n + Number(v), 0);
    expect(sum).toBe(241);
    expect(Object.values(BINDER_COUNTS).reduce((n, v) => n + v, 0)).toBe(241);
    expect(BINDER_PARTS.returns + BINDER_PARTS.secondParts).toBe(241);
  });

  it("BND-01 acceptance: statuses come only from §3.3.1 Binder", async () => {
    show("c");
    const list = await rows();
    const words = new Set(
      list.map((r) => r.querySelectorAll("td")[4]?.querySelector("span span")?.textContent),
    );
    for (const w of words) {
      expect(["Draft", "Published", "Unpublished", "Complete", "Closed"]).toContain(w);
    }
  });

  it("BND-01 acceptance: Gathering returns are Published, Quintero a Draft, accepted returns Closed", async () => {
    show("a");
    await rows();
    for (const c of [
      "Estate of Walter Thornbury",
      "Gloria Mendez",
      "Morgan & Kai Ferris",
      "Lakeshore Literacy Alliance",
      "Fenwick Family Foundation",
    ]) {
      expect(statusOf(rowOf(c)), c).toBe("Published");
    }
    expect(statusOf(rowOf("Rafael Quintero"))).toBe("Draft");
    expect(statusOf(rowOf("Marcus & Dana Whitley"))).toBe("Closed");
    expect(statusOf(rowOf("Copperleaf Coffee Roasters, Inc."))).toBe("Closed");
  });

  it("BND-01 acceptance: the Feld row reads 5 of 7, Published (2 open)", async () => {
    show("a");
    await rows();
    const feld = rowOf("Jonah & Claire Feld");
    expect(cell(feld, 3)).toBe("5 of 7");
    expect(statusOf(feld)).toBe("Published");
    expect(cell(rowOf("Meera Shah"), 3)).toBe("15 of 17");
  });

  it("BND-01 acceptance: last-activity dates agree with HOME-01 and the Inbox", async () => {
    show("a");
    await rows();
    expect(cell(rowOf("Jonah & Claire Feld"), 5)).toBe("9:12 AM");
    expect(cell(rowOf("Gloria Mendez"), 5)).toBe("Yesterday");
    expect(cell(rowOf("Calloway Family Trust"), 5)).toBe("Sep 9");
    expect(cell(rowOf("Estate of Walter Thornbury"), 5)).toBe("Sep 9");
    expect(cell(rowOf("Rafael Quintero"), 5)).toBe("—");
    // Fenwick, Aug 11, is 34 days silent on the demo clock: the date reads in brick.
    const fenwick = rowOf("Fenwick Family Foundation").querySelectorAll("td")[5];
    expect(fenwick?.textContent).toBe("Aug 11");
    expect(fenwick?.querySelector("[data-silent]")).not.toBeNull();
    expect(rowOf("Ridgeline Property Partners, LP").querySelector("[data-silent]")).toBeNull();
  });

  it("BND-01 acceptance: T1 grammar: 50px filter bar, tiles that filter, one pane, centred title", async () => {
    show("a");
    await rows();
    const bar = screen.getByRole("toolbar", { name: "Filters" });
    expect(bar.className).toContain("h-[50px]");
    expect(document.querySelectorAll("[data-template='T1'] section")).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "Binders" }).className).toContain("text-center");
  });
});

describe("BND-01 route /binders", () => {
  function route(scenario: Scenario): void {
    install(scenario);
    const Page = bindersRoute.options.component as () => JSX.Element;
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Page />
      </QueryClientProvider>,
    );
  }

  it("flag off (binders.engine): the flag-off state, never a 404", async () => {
    route(scenarios.a);
    expect(await screen.findByText("Binders is not turned on for this firm.")).toBeTruthy();
    expect(document.querySelector("[data-flag-off='binders.engine']")).not.toBeNull();
  });

  it("flag on: BND-01 on the current season", async () => {
    const base = scenarios.a.handlers["GET /v1/me/capabilities"];
    route({
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        "GET /v1/me/capabilities": async (request) => {
          const body = (await (base?.(request) ?? json({}))).json() as Promise<
            Record<string, unknown>
          >;
          return json({ ...(await body), flags: { "binders.engine": true } });
        },
      },
    });
    expect(await screen.findByText("Showing 15 of 241")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Season: TY2025" })).toBeTruthy();
  });
});

describe("BND-01 behaviour", () => {
  it("the tiles filter the rows and never count themselves out", async () => {
    const seen = show("a");
    await rows();
    fireEvent.click(screen.getByRole("button", { name: /Complete/ }));
    expect(await screen.findByText("Showing 4 of 40")).toBeTruthy();
    const shown = [...document.querySelectorAll<HTMLElement>("tr[data-row]")];
    expect(shown.map(statusOf)).toEqual(["Complete", "Complete", "Complete", "Complete"]);
    expect(tiles().Published).toBe("48");
    expect(
      seen.calls.some((c) => c.path === "/v1/binders" && c.query.includes("status=complete")),
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /Complete/ }));
    expect(await screen.findByText("Showing 15 of 241")).toBeTruthy();
  });

  it("a search that matches nothing shows the filtered-empty state", async () => {
    show("a");
    await rows();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search binders" }), {
      target: { value: "Ashford" },
    });
    expect(await screen.findByText("No results for ‘Ashford’.")).toBeTruthy();
  });

  it("Publish from the row menu publishes the Draft and offers Undo", async () => {
    const seen = show("a");
    await rows();
    const menu = openMenu(rowOf("Rafael Quintero"));
    expect(within(menu).queryByRole("menuitem", { name: /Unpublish/ })).toBeNull();
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Publish" }));
    await waitFor(() => {
      expect(tiles().Draft).toBe("0");
    });
    expect(tiles().Published).toBe("49");
    const call = seen.calls.find((c) => c.path.endsWith("/publish"));
    expect(call?.method).toBe("POST");
    const toast = toastStore.list()[0];
    expect(toast?.text).toBe("Published 2025 Binder · Rafael Quintero");
    expect(toast?.action).toBe("Undo");
  });

  it("Unpublish… asks for a reason and sends it", async () => {
    const seen = show("a");
    await rows();
    const menu = openMenu(rowOf("Gloria Mendez"));
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Unpublish…" }));
    const dialog = await screen.findByRole("dialog", { name: "Unpublish binder" });
    const confirm = within(dialog).getByRole("button", { name: "Unpublish" });
    expect(confirm.hasAttribute("disabled")).toBe(true);
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Reason" }), {
      target: { value: "fixing 2 requests" },
    });
    fireEvent.click(confirm);
    await waitFor(() => {
      expect(statusOf(rowOf("Gloria Mendez"))).toContain("Unpublished");
    });
    const call = seen.calls.find((c) => c.path.endsWith("/unpublish"));
    expect(call?.body).toEqual({ reason: "fixing 2 requests" });
  });

  it("the menu offers Duplicate as pt 2 and Open in Files (planned, disabled)", async () => {
    show("a");
    await rows();
    const menu = openMenu(rowOf("Jonah & Claire Feld"));
    expect(within(menu).getByRole("menuitem", { name: "Duplicate as pt 2" })).toBeTruthy();
    expect(
      within(menu).getByRole("menuitem", { name: "Open in Files" }).getAttribute("aria-disabled"),
    ).toBe("true");
  });

  it("New binder… opens the sheet: client, work item, template; Create posts a Draft", async () => {
    const seen = show("a");
    await rows();
    fireEvent.click(await screen.findByRole("button", { name: "New binder…" }));
    const sheet = await screen.findByRole("dialog", { name: "New binder" });
    const create = within(sheet).getByRole("button", { name: "Create" });
    expect(create.hasAttribute("disabled")).toBe(true);
    for (const label of ["Client", "Work item", "Template"]) {
      expect(within(sheet).getByText(label)).toBeTruthy();
    }
    expect(seen.calls.some((c) => c.path === "/v1/engagements")).toBe(true);
  });

  it("no control on the screen is an agent-owned send, approve or sign-off", async () => {
    show("a");
    await rows();
    for (const word of [/Approve/, /Sign off/, /Release/, /^Send$/, /^Post$/]) {
      expect(screen.queryByRole("button", { name: word })).toBeNull();
    }
  });
});
