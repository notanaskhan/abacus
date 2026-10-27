// ADM-07 · Audit log explorer (G-02-T13). One test per artboard (a–g, and c's values-withheld
// variant) on its fixture scenario (SPEC-349 AC-1, AC-2, AC-5 to AC-7, AC-10, AC-12; INV-1,
// INV-5), plus: no row names the agent as an actor, no edit or delete affordance, the IP filters
// the feed, and the drawer's footer says events are immutable. axe runs in the Playwright
// journey (G-02-T21), not here.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { AuditLogPage } from ".";
import { type Adm07State, OPENS, scenarios } from "./scenarios";

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

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function show(state: Adm07State, initial: string = OPENS[state]): Call[] {
  const scenario: Scenario = scenarios[state];
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AuditLogPage initial={initial} />
    </QueryClientProvider>,
  );
  return calls;
}

const feed = async (): Promise<HTMLElement[]> => {
  const list = await screen.findByRole("list", { name: "Audit log" });
  return within(list).getAllByRole("listitem");
};

describe("ADM-07 Audit log explorer", () => {
  it("a: fourteen rows newest first, the count with its lock and the policy-principal note", async () => {
    show("a");
    const rows = await feed();
    expect(rows).toHaveLength(14);
    expect(rows[0]?.textContent).toContain("Engagement run started by Marcus Delaney");
    expect(rows[0]?.textContent).toContain("Plan approved ('yes, run it') · Auto mode off");
    expect(rows[3]?.textContent).toContain(
      "Entries approved by Raj Malhotra under BH AJE thresholds v2",
    );
    expect(rows[2]?.textContent).toContain(
      "Lena Park ✕ Ashford Manufacturing Co. · approved by Margaret Okonkwo",
    );
    expect(rows[5]?.textContent).toContain("Report prepared by Hannah Leclerc via Agent");
    expect(rows[5]?.textContent).toContain(
      "Season Progress Reporter · scheduled Mondays 9:00 AM CT · 2 m 41 s · 1 artifact",
    );
    expect(rows[9]?.textContent).toContain("Signed in by Neil Ashcroft");
    expect(rows[13]?.textContent).toContain("Routing check only — not an approval");
    expect(screen.getByText(/18,406 events · immutable/)).toBeTruthy();
    expect(
      screen.getByText("Policy principal: 0 events — policy acceptance is off (AI policy v3)."),
    ).toBeTruthy();
    expect(screen.getByText(/Showing 14 of 18,406/)).toBeTruthy();
  });

  it("a, INV-1: no row reads Accrued Agent and nothing edits or deletes an event", async () => {
    show("a");
    await feed();
    expect(document.body.textContent).not.toContain("Accrued Agent");
    expect(screen.queryByRole("button", { name: /edit|delete|remove/i })).toBeNull();
  });

  it("b: via Agent lists rows 6, 9, 11 and 14 and counts 4 of 1,962", async () => {
    show("b");
    const rows = await feed();
    expect(rows).toHaveLength(4);
    for (const row of rows) expect(row.textContent).toContain("via Agent");
    expect(screen.getByText(/^4 of 1,962$/)).toBeTruthy();
    expect(screen.getByText("Showing 4 of 1,962")).toBeTruthy();
  });

  it("c: Margaret reads the Copperleaf values: the batch foots to 20,020.00", async () => {
    show("c");
    const drawer = await screen.findByRole("dialog");
    await within(drawer).findByText(/^Within BH AJE thresholds v2/);
    expect(drawer.textContent).toContain("Within BH AJE thresholds v2");
    expect(drawer.textContent).toContain("198.51.100.57 · Chrome · macOS");
    expect(drawer.textContent).toContain("sha256 9f3c…a71e");
    const table = within(drawer).getByRole("table");
    expect(table.textContent).toContain("11,860.00");
    expect(table.textContent).toContain("20,020.00");
    expect(drawer.textContent).toContain("Accrued expenses");
    expect(drawer.textContent).toContain("Priya Raman");
    expect(drawer.textContent).toContain("Proposed by Raj Malhotra via Agent · Close run 2");
    expect(drawer.textContent).toContain("Immutable. Corrections are new events.");
  });

  it("c (Felix): values are withheld with the reason", async () => {
    show("c_withheld");
    const drawer = await screen.findByRole("dialog");
    await within(drawer).findByText("Values are visible to partners in scope.");
    expect(within(drawer).queryByRole("table")).toBeNull();
  });

  it("d: the dormant policy principal reads 'Policy: BH AJE thresholds v2' and 2 events", async () => {
    show("d");
    const rows = await feed();
    const text = rows.map((r) => r.textContent).join("\n");
    expect(text).toContain("Entries accepted by Policy: BH AJE thresholds v2");
    expect(text).toContain("Acceptance reversed by Priya Raman");
    expect(screen.getByText("Policy principal: 2 events")).toBeTruthy();
  });

  it("e → g: Export… asks Sep 8–14 with values and toasts the ready manifest", async () => {
    const calls = show("e");
    await feed();
    fireEvent.click(screen.getByRole("button", { name: /Export…/ }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("CSV + signed JSON manifest");
    expect(
      within(dialog).getByRole("switch", { name: "Include before/after values" }),
    ).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Export" }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(
        "Export ready · SHA-256 manifest included",
      );
    });
    const post = calls.find((c) => c.method === "POST" && c.path === "/v1/audit-events/exports");
    expect(post?.body).toMatchObject({
      from_date: "2026-09-08",
      to_date: "2026-09-14",
      include_values: true,
    });
  });

  it("f: a search with no match says so and what search covers", async () => {
    show("f");
    await screen.findByText("No events match 'pell street iii'.");
    expect(screen.getByText("Search covers actors, objects and details.")).toBeTruthy();
  });

  it("an IP click filters the feed to that IP", async () => {
    show("a");
    await feed();
    const [ip] = screen.getAllByRole("button", { name: "Filter by IP 198.51.100.44" });
    if (ip === undefined) throw new Error("no IP button");
    fireEvent.click(ip);
    await waitFor(async () => {
      const rows = await feed();
      expect(rows).toHaveLength(2);
    });
  });

  it("each row is a button named title, object and time", async () => {
    show("a");
    await feed();
    expect(
      screen.getByRole("button", {
        name: /^Engagement run started by Marcus Delaney, Northwind Robotics 401\(k\) Plan · PY2025 EBP Audit, /,
      }),
    ).toBeTruthy();
  });
});
