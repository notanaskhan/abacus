// CLI-01 · Clients index (P-07-T12). One test per artboard (a–f) on its fixture scenario, the
// spec's acceptance checklist, P-07 Stories 1.1 and 1.2, the error state, "Load more", the row
// ··· menu and the route.
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
import { type ClientFilters, DEFAULT_CLIENT_FILTERS } from "../../domain/clients";
import { clientsRoute } from "../../routes/firm/clients";
import { newQueryClient } from "../../testing/support";
import { CLI01 } from ".";
import { type Cli01State, SEARCH, STATES, scenarios } from "./scenarios";

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
  calls: { method: string; path: string; query: string }[];
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
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return seen;
}

function Harness({ initial }: { initial: ClientFilters }): JSX.Element {
  const [filters, setFilters] = useState(initial);
  return <CLI01 filters={filters} onFilters={setFilters} />;
}

function show(state: Cli01State, scenario: Scenario = scenarios[state]): Seen {
  const seen = install(scenario);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Harness initial={{ ...DEFAULT_CLIENT_FILTERS, ...SEARCH[state] }} />
    </QueryClientProvider>,
  );
  return seen;
}

function rows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("tr[data-row]")];
}

function names(): string[] {
  return rows().map((r) => r.querySelector("td span span")?.textContent ?? "");
}

function rowOf(name: string): HTMLElement {
  const row = rows().find((r) => r.querySelector("td span span")?.textContent === name);
  if (row === undefined) throw new Error(`no row for ${name}`);
  return row;
}

function cell(row: HTMLElement, index: number): string {
  return row.querySelectorAll("td")[index]?.textContent ?? "";
}

const COL = {
  client: 0,
  type: 1,
  entities: 2,
  services: 3,
  office: 4,
  partner: 5,
  portal: 6,
  open: 7,
  activity: 8,
} as const;

function openMenu(row: HTMLElement): HTMLElement {
  const trigger = within(row).getByRole("button", { name: /actions$/ });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  return screen.getByRole("menu");
}

const NAMED = [
  "Jonah & Claire Feld",
  "Copperleaf Coffee Roasters, Inc.",
  "Meera Shah",
  "Northwind Robotics, Inc.",
  "Ridgeline Property Partners, LP",
  "Granite Peak Outdoor Supply, Inc.",
  "Harborview Dental Properties, LP",
  "Marcus & Dana Whitley",
  "Walter Thornbury",
  "Bluestem Analytics, LLC",
  "Lakeshore Literacy Alliance",
  "Elena Varga",
  "Calloway Family Trust",
  "Ashford Manufacturing Co.",
  "Juniper & Oak Interiors, LLC",
  "Daniel & Ruth Okafor",
];

describe("CLI-01 artboards", () => {
  it("has a scenario for every artboard a–f", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
    expect(scenarios.c.persona).toBe("lena-park");
    for (const s of STATES) expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
  });

  it("CLI-01a default: 184 clients, the 16 named newest first, Load more", async () => {
    show("a");
    expect(await screen.findByText("184 clients")).toBeTruthy();
    expect(names()).toEqual(NAMED);
    const feld = rowOf("Jonah & Claire Feld");
    expect(cell(feld, COL.client)).toContain("Brooklyn, NY · MFJ");
    expect(cell(feld, COL.type)).toBe("Household");
    expect(cell(feld, COL.office)).toBe("New York");
    expect(cell(feld, COL.partner)).toBe("DR");
    expect(cell(feld, COL.portal)).toBe("Active");
    expect(cell(feld, COL.activity)).toBe("9:12 AM · Documents uploaded");
    expect(screen.getByRole("button", { name: "Load more" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Status: Active" })).toBeTruthy();
    // The default is not a narrowing: no Clear.
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
  });

  it("CLI-01b Service line │ Audit: Northwind, Granite Peak and Lakeshore lead, Showing n", async () => {
    const seen = show("b");
    expect(await screen.findByText("Showing 25")).toBeTruthy();
    expect(names().slice(0, 3)).toEqual([
      "Northwind Robotics, Inc.",
      "Granite Peak Outdoor Supply, Inc.",
      "Lakeshore Literacy Alliance",
    ]);
    expect(seen.calls.some((c) => c.query.includes("service_line=audit"))).toBe(true);
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
  });

  it("CLI-01c Lena Park: Ashford is absent and nothing says a client is hidden (DEC-43)", async () => {
    show("c");
    expect(await screen.findByText("183 clients")).toBeTruthy();
    expect(names()).not.toContain("Ashford Manufacturing Co.");
    expect(names().slice(0, 15)).toEqual(NAMED.filter((n) => n !== "Ashford Manufacturing Co."));
    const text = document.body.textContent;
    expect(text).not.toMatch(/hidden|ethical wall|restricted/i);
    expect(text).not.toContain("Ashford");
  });

  it("CLI-01d Schwab: No clients match 'Schwab'. and Clear filters", async () => {
    show("d");
    expect(await screen.findByText("No clients match 'Schwab'.")).toBeTruthy();
    fireEvent.click(screen.getByText("Clear filters"));
    expect(await screen.findByText("184 clients")).toBeTruthy();
  });

  it("CLI-01e loading: the header and column heads stay, 8 skeleton rows, no count", async () => {
    show("e");
    expect(screen.getByRole("heading", { name: "Clients" })).toBeTruthy();
    expect(screen.getAllByRole("columnheader").length).toBeGreaterThanOrEqual(9);
    await waitFor(() => {
      expect(document.querySelectorAll("[data-skeleton] [data-row]").length).toBe(8);
    });
    expect(screen.queryByText(/clients$/)).toBeNull();
  });

  it("CLI-01f empty firm: No clients yet. with + New client and Import…", async () => {
    show("f");
    expect(await screen.findByText("No clients yet.")).toBeTruthy();
    expect(
      screen.getByText("Add a client or import your client list from CCH Axcess Tax or a CSV."),
    ).toBeTruthy();
    expect((await screen.findAllByRole("button", { name: "New client" })).length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByRole("button", { name: "Import…" }).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^\d+ clients$/)).toBeNull();
  });

  it("error: the C-20 error row with Retry", async () => {
    show("a", {
      ...scenarios.a,
      handlers: { ...scenarios.a.handlers, "GET /v1/clients": () => json({}, 500) },
    });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });
});

describe("CLI-01 acceptance", () => {
  it("CLI-01 acceptance: split filter chips with the active Status chip; one pane, centred title", async () => {
    show("a");
    await screen.findByText("184 clients");
    const bar = screen.getByRole("toolbar", { name: "Filters" });
    expect(bar.className).toContain("h-[50px]");
    for (const chip of ["Type: All", "Office: All offices", "Partner: All", "Service line: All"]) {
      expect(within(bar).getByRole("button", { name: chip })).toBeTruthy();
    }
    expect(document.querySelectorAll("[data-template='T1'] section")).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "Clients" }).className).toContain("text-center");
    expect(screen.getByPlaceholderText("Search clients, entities, contacts")).toBeTruthy();
  });

  it("CLI-01 acceptance: open requests Northwind 13, Ridgeline 5, Feld 2, Copperleaf 2; Granite Peak Binder draft", async () => {
    show("a");
    await screen.findByText("184 clients");
    expect(cell(rowOf("Northwind Robotics, Inc."), COL.open)).toBe("13");
    expect(cell(rowOf("Ridgeline Property Partners, LP"), COL.open)).toBe("5");
    expect(cell(rowOf("Jonah & Claire Feld"), COL.open)).toBe("2");
    expect(cell(rowOf("Copperleaf Coffee Roasters, Inc."), COL.open)).toBe("2");
    expect(cell(rowOf("Granite Peak Outdoor Supply, Inc."), COL.open)).toBe("Binder draft");
    expect(cell(rowOf("Elena Varga"), COL.open)).toBe("—");
  });

  it("CLI-01 acceptance: entity counts Northwind 2, Granite Peak 2, Thornbury 2; others 1", async () => {
    show("a");
    await screen.findByText("184 clients");
    const two = new Set([
      "Northwind Robotics, Inc.",
      "Granite Peak Outdoor Supply, Inc.",
      "Walter Thornbury",
    ]);
    for (const name of NAMED) {
      expect(cell(rowOf(name), COL.entities), name).toBe(two.has(name) ? "2" : "1");
    }
  });

  it("CLI-01 acceptance: Attest only on Northwind, Granite Peak and Lakeshore", async () => {
    show("a");
    await screen.findByText("184 clients");
    const attest = NAMED.filter((n) => cell(rowOf(n), COL.type).includes("Attest"));
    expect(attest).toEqual([
      "Northwind Robotics, Inc.",
      "Granite Peak Outdoor Supply, Inc.",
      "Lakeshore Literacy Alliance",
    ]);
    expect(cell(rowOf("Copperleaf Coffee Roasters, Inc."), COL.services)).toBe("CASTax");
    expect(cell(rowOf("Juniper & Oak Interiors, LLC"), COL.services)).toBe("CAS");
  });

  it("CLI-01 acceptance: the Thornbury portal reads Invited; the client is Walter Thornbury (DEC-62)", async () => {
    show("a");
    await screen.findByText("184 clients");
    expect(cell(rowOf("Walter Thornbury"), COL.portal)).toBe("Invited");
    expect(names()).not.toContain("Estate of Walter Thornbury");
  });

  it("CLI-01 acceptance: no TINs anywhere in the list", async () => {
    show("a");
    await screen.findByText("184 clients");
    const text = document.body.textContent;
    expect(text).not.toMatch(/\d{2}-\d{7}|\d{3}-\d{2}-\d{4}|XX-XXX|•••-••/);
  });

  it("P-07 Story 1.1: Load more appends the next keyset page; there are no page numbers", async () => {
    const seen = show("a");
    await screen.findByText("184 clients");
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    await waitFor(() => {
      expect(rows()).toHaveLength(32);
    });
    expect(names().slice(0, 16)).toEqual(NAMED);
    expect(seen.calls.filter((c) => c.path === "/v1/clients").at(-1)?.query).toContain("cursor=");
    expect(screen.queryByRole("navigation", { name: /page/i })).toBeNull();
    expect(screen.getByText("184 clients")).toBeTruthy();
  });
});

describe("CLI-01 behaviour", () => {
  it("the search is sent as q and narrows the rows", async () => {
    const seen = show("a");
    await screen.findByText("184 clients");
    fireEvent.change(screen.getByRole("searchbox", { name: "Search clients" }), {
      target: { value: "Northwind" },
    });
    expect(await screen.findByText("Showing 1")).toBeTruthy();
    expect(names()).toEqual(["Northwind Robotics, Inc."]);
    expect(seen.calls.some((c) => c.query.includes("q=Northwind"))).toBe(true);
  });

  it("the row menu copies the client ID with a toast; planned targets are disabled", async () => {
    show("a");
    await screen.findByText("184 clients");
    const menu = openMenu(rowOf("Jonah & Claire Feld"));
    for (const planned of ["Open", "Message", "New engagement"]) {
      expect(
        within(menu).getByRole("menuitem", { name: planned }).getAttribute("aria-disabled"),
      ).toBe("true");
    }
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Copy client ID" }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Client ID copied");
    });
  });

  it("Lena Park (no client.intake) sees no New client or Import…", async () => {
    show("c");
    await screen.findByText("183 clients");
    expect(screen.queryByRole("button", { name: "New client" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Import…" })).toBeNull();
  });

  it("no control on the screen is an agent-owned send, approve or sign-off", async () => {
    show("a");
    await screen.findByText("184 clients");
    for (const word of [/Approve/, /Sign off/, /Release/, /^Send$/, /^Post$/]) {
      expect(screen.queryByRole("button", { name: word })).toBeNull();
    }
  });
});

describe("CLI-01 route /clients", () => {
  it("serves CLI-01 for every firm (clients.v2 retired, P-07-T59)", async () => {
    install(scenarios.a);
    const Page = clientsRoute.options.component as () => JSX.Element;
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Page />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("184 clients")).toBeTruthy();
    expect(document.querySelector("[data-screen='CLI-01']")).not.toBeNull();
  });
});
