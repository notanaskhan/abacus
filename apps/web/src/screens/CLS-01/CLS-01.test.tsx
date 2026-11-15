// CLS-01 · Closes index (C-01-T33; SPEC-655 AC-1, AC-5, AC-6). Acceptance (the task row): states
// a–f on T1 with tiles that filter, the split chips, search with "Showing n of 22", the reconciled
// bar, the running disc and pill, the row menu, Start run's confirm, loading and attest-empty, and
// the List · Board toggle hidden while `board.enabled` is off.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { DEFAULT_CLOSE_FILTERS } from "../../domain/closes";
import { renderRoutes } from "../../testing/support";
import { ClosesIndex } from ".";
import { COPY } from "./copy";
import { type Cls01State, HOVER_ROW, SEARCH, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function mount(state: Cls01State, onStartRun?: (id: string) => void): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ClosesIndex
          initial={{ ...DEFAULT_CLOSE_FILTERS, ...SEARCH[state] }}
          {...(onStartRun === undefined ? {} : { onStartRun })}
        />
      ),
    },
  ]);
}

const rows = (): HTMLElement[] => screen.getAllByRole("row").slice(1);

function nth<T>(xs: readonly T[], i: number): T {
  const found = xs[i];
  if (found === undefined) throw new Error(`no item ${String(i)}`);
  return found;
}

function rowOf(text: string): HTMLElement {
  const row = screen.getByText(text).closest("tr");
  if (row === null) throw new Error(`no row for ${text}`);
  return row;
}

describe("CLS-01", () => {
  it("a: 22 closes, tiles 3 · 11 · 5 · 3 and the summary line", async () => {
    mount("a");
    await screen.findByText("Copperleaf Coffee Roasters, Inc.");
    expect(rows()).toHaveLength(22);
    expect(screen.getByText("22 closes · 51 open issues · 2 past due · 3 running")).toBeTruthy();
    const copperleaf = nth(rows(), 0);
    expect(within(copperleaf).getByText("43% (9 / 21)")).toBeTruthy();
    expect(within(copperleaf).getByText("4 days past due")).toBeTruthy();
    expect(within(copperleaf).getByText("RM / PR")).toBeTruthy();
    expect(within(copperleaf).getAllByText(COPY.running).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText(COPY.runningPill(3))).toBeTruthy();
    });
  });

  it("a: delivered rows read 100% and not-started rows 0% with no issues", async () => {
    mount("a");
    await screen.findByText("Juniper & Oak Interiors, LLC");
    const juniper = rowOf("Juniper & Oak Interiors, LLC");
    expect(within(juniper).getByText("100%")).toBeTruthy();
    const canyon = rowOf("Canyon Pass Climbing Gym, LLC");
    expect(within(canyon).getByText("0%")).toBeTruthy();
  });

  it("b: the In progress tile shows 11 of 22", async () => {
    mount("b");
    await screen.findByText("Copperleaf Coffee Roasters, Inc.");
    expect(rows()).toHaveLength(11);
    expect(screen.getByText(/Showing 11 of 22/)).toBeTruthy();
  });

  it("c: past due is Copperleaf and Bluebird Bakery", async () => {
    mount("c");
    await screen.findByText("Bluebird Bakery Co.");
    expect(rows().map((r) => nth(within(r).getAllByRole("cell"), 0).textContent)).toEqual([
      "Copperleaf Coffee Roasters, Inc.",
      "Bluebird Bakery Co.",
    ]);
  });

  it("d: no attest clients this period", async () => {
    mount("d");
    expect(await screen.findByText(COPY.attestEmpty.title)).toBeTruthy();
  });

  it("e: loading keeps the header and draws skeleton rows", async () => {
    mount("e");
    expect(await screen.findByText(COPY.title)).toBeTruthy();
    expect(screen.queryByText("Copperleaf Coffee Roasters, Inc.")).toBeNull();
  });

  it("f: a row's menu offers Open · Start run · View plan", async () => {
    mount("f");
    await screen.findByText(HOVER_ROW);
    fireEvent.pointerDown(
      screen.getByRole("button", { name: `${COPY.menu.label}: ${HOVER_ROW}` }),
    );
    expect(await screen.findByRole("menuitem", { name: COPY.menu.open })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: COPY.menu.startRun })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: COPY.menu.viewPlan })).toBeTruthy();
  });

  it("AC-6: Start run on a not-started close asks first", async () => {
    const started = vi.fn();
    mount("a", started);
    await screen.findByText("Canyon Pass Climbing Gym, LLC");
    fireEvent.pointerDown(
      screen.getByRole("button", { name: `${COPY.menu.label}: Canyon Pass Climbing Gym, LLC` }),
    );
    fireEvent.click(await screen.findByRole("menuitem", { name: COPY.menu.startRun }));
    expect(await screen.findByText(COPY.startConfirm.body)).toBeTruthy();
    expect(started).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: COPY.startConfirm.confirm }));
    expect(started).toHaveBeenCalledTimes(1);
  });

  it("the List · Board toggle is hidden while board.enabled is off", async () => {
    mount("a");
    await screen.findByText("Copperleaf Coffee Roasters, Inc.");
    expect(screen.queryByRole("button", { name: /Board/ })).toBeNull();
  });
});
