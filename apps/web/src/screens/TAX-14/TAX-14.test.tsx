// T-08-T31 (TASK-9032; DEC-6037): TAX-14 a-e from their scenarios, whose rows are the exported
// Python scenario's. Row acceptance: "TAX-14 A-E render from data, the run updates live, and Run
// on selection re-runs only the checked rows."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { firmOffices } from "../../fixtures/seed/firm-people";
import { tax14Run } from "../../fixtures/scenarios/TAX-14";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { TAX14 } from "./index";
import { INITIAL, OTHER_VERSIONS, type Tax14State, scenarios } from "./scenarios";

let restore: (() => void) | null = null;
interface Call {
  method: string;
  path: string;
  body: unknown;
}

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
  toastStore.clear();
});

function show(state: Tax14State, over: Record<string, FixtureHandler> = {}): Call[] {
  const calls: Call[] = [];
  const base = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...base.handlers, ...over }).map(([k, h]) => [
      k,
      ((r) => {
        calls.push({ method: r.method, path: r.path, body: r.body });
        return h(r);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...base, handlers });
  const init = INITIAL[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <TAX14
          {...(init.picker === undefined ? {} : { initialPicker: init.picker })}
          {...(init.selectNone === undefined ? {} : { selectNone: init.selectNone })}
          versions={OTHER_VERSIONS}
        />
      ),
    },
  ]);
  return calls;
}

function row(client: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-row="${client}"]`);
  if (found === null) throw new Error(`no row ${client}`);
  return found;
}

const tile = (key: string) => document.querySelector(`[data-tile="${key}"]`)?.textContent ?? "";

describe("TAX-14 Firm standards run", () => {
  it("TAX-14a running: six rows, tiles 0 · 1 · 3 · 2, Ridgeline linked, Marlowe created", async () => {
    show("a");
    await screen.findByText(C.pane(6), { selector: "span" });
    expect(document.querySelectorAll("[data-row]")).toHaveLength(6);
    expect(tile("queued")).toContain("0");
    expect(tile("running")).toContain("1");
    expect(tile("passed")).toContain("3");
    expect(tile("exceptions")).toContain("2");
    expect(screen.getByText(C.summary(6, 6))).toBeTruthy();
    expect(screen.getByText("1065 Review Checklist v4 · 42 checks")).toBeTruthy();
    expect(screen.getByText("Started 9:18 AM · Samuel Ito")).toBeTruthy();
    const ridgeline = row("Ridgeline Property Partners, LP");
    expect(within(ridgeline).getByText("2 exceptions")).toBeTruthy();
    expect(within(ridgeline).getByText("40 of 42")).toBeTruthy();
    expect(within(ridgeline).getByText(/Linked to 2 existing issues/)).toBeTruthy();
    expect(within(ridgeline).getByText("OB / SI")).toBeTruthy();
    expect(within(row("Marlowe Street Holdings, LP")).getByText(/3 issues created/)).toBeTruthy();
    expect(within(row("Northgate Medical Partners, LLP")).getByText(C.running)).toBeTruthy();
    expect(within(row("Northgate Medical Partners, LLP")).getByText("31 of 42")).toBeTruthy();
  });

  it("TAX-14a: Ridgeline expands to its checks, two linked exceptions", async () => {
    show("a");
    const ridgeline = await waitFor(() => row("Ridgeline Property Partners, LP"));
    fireEvent.click(within(ridgeline).getByRole("button", { name: /Ridgeline/ }));
    const checks = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-tax14="checks"]');
      if (found === null || found.querySelectorAll("[data-check]").length === 0) {
        throw new Error("no checks");
      }
      return found;
    });
    expect(checks.querySelectorAll("[data-check]")).toHaveLength(8);
    expect(
      within(checks).getByText(/C-17 Schedule M-2 line 9 equals Schedule L line 21/),
    ).toBeTruthy();
    expect(within(checks).getAllByText(C.linkedCheck)).toHaveLength(2);
    expect(within(checks).getByText(C.linkedNote)).toBeTruthy();
  });

  it("TAX-14b complete: Northgate passed, tiles 0 · 0 · 4 · 2, Complete · 9:26 AM", async () => {
    show("b");
    await screen.findByText("Complete · 9:26 AM");
    expect(tile("running")).toContain("0");
    expect(tile("passed")).toContain("4");
    expect(within(row("Northgate Medical Partners, LLP")).getByText("42 of 42")).toBeTruthy();
  });

  it("TAX-14 acceptance: the run updates live and the toast names the counts on completion", async () => {
    let reads = 0;
    const offices = firmOffices();
    show("a", {
      "GET /v1/standards-runs": () => {
        reads += 1;
        return json({ items: [tax14Run(reads < 2 ? "a" : "b", offices)], next_cursor: null });
      },
    });
    await screen.findByText(C.pane(6), { selector: "span" });
    await waitFor(
      () => {
        expect(toastStore.list().map((t) => t.text)).toContain(C.complete(4, 2));
      },
      { timeout: 5_000 },
    );
    expect(within(row("Northgate Medical Partners, LLP")).getByText("42 of 42")).toBeTruthy();
  });

  it("TAX-14c queued: every disc an empty ring and every result Queued", async () => {
    show("c");
    await screen.findByText(C.pane(6), { selector: "span" });
    for (const r of document.querySelectorAll<HTMLElement>("[data-row]")) {
      expect(within(r).getByText(C.queued)).toBeTruthy();
      expect(within(r).getByRole("img", { name: C.status.queued })).toBeTruthy();
    }
    expect(tile("queued")).toContain("6");
  });

  it("TAX-14d standard picker: the versions and the Knowledge link", async () => {
    show("d");
    expect(await screen.findByText("1065 Review Checklist v4 (current)")).toBeTruthy();
    expect(screen.getByText("1065 Review Checklist v3 (superseded)")).toBeTruthy();
    expect(screen.getByText(C.knowledge)).toBeTruthy();
  });

  it("TAX-14e empty selection: nothing is run until a return is checked", async () => {
    show("e");
    expect(await screen.findByText(C.emptySelection)).toBeTruthy();
    expect(screen.getByRole("button", { name: C.runSelection }).hasAttribute("disabled")).toBe(
      true,
    );
  });

  it("TAX-14 acceptance: Run on selection re-runs only the checked rows", async () => {
    const calls = show("b");
    await screen.findByText("Complete · 9:26 AM");
    fireEvent.click(screen.getByRole("checkbox", { name: C.selectAll })); // none
    fireEvent.click(
      screen.getByRole("checkbox", { name: C.select("Ridgeline Property Partners, LP") }),
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: C.select("Marlowe Street Holdings, LP") }),
    );
    fireEvent.click(screen.getByRole("button", { name: C.runSelection }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith(":rerun"))).toBe(true);
    });
    const sent = calls.find((c) => c.path.endsWith(":rerun"))?.body as { return_ids: string[] };
    const run = tax14Run("b", firmOffices());
    const ids = (name: string) => run.items.find((i) => i.client_name === name)?.work_item_id;
    expect(new Set(sent.return_ids)).toEqual(
      new Set([ids("Ridgeline Property Partners, LP"), ids("Marlowe Street Holdings, LP")]),
    );
  });

  it("error: a failed read offers Retry", async () => {
    show("a", { "GET /v1/standards-runs": () => json({ detail: "boom" }, 500) });
    expect(await screen.findByRole("button", { name: C.retry })).toBeTruthy();
  });
});
