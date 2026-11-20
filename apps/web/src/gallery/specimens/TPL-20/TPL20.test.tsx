import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SURL_SHEET } from "../../../fixtures/seed/granite-peak-fy2026-surl-sheet";
import {
  TPL20_SCENARIOS,
  TPL20_STATES,
  Tpl20Artboard,
  Tpl20Board,
  tpl20Rows,
  tpl20Sections,
  tpl20SignOffs,
} from ".";

// F-08-T09 (TASK-8748; docs/screens/TPL-20.md): "TPL-20a to g render at their spec clocks with
// '40 rows · 1 exception', 0 adopted in a, and P CH / R HL locked on every row in e." One state
// test per letter; every figure is the T02 seed's.

afterEach(cleanup);

function wrap(node: ReactNode): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

function board(state: (typeof TPL20_STATES)[number], open = vi.fn(), onIntent = vi.fn()) {
  render(wrap(<Tpl20Board state={state} onOpenSignOff={open} onIntent={onIntent} />));
  return { open, onIntent };
}

const statusBar = (): string => document.body.textContent;

describe("TPL-20: scenarios", () => {
  it("each letter has its spec clock and Cole Hart", () => {
    expect(TPL20_SCENARIOS.a.clock).toBe("2026-09-28T17:00:00-05:00");
    expect(TPL20_SCENARIOS.b.clock).toBe("2026-09-27T18:20:00-05:00");
    expect(TPL20_SCENARIOS.e.clock).toBe("2026-10-01T16:30:00-05:00");
    expect(TPL20_SCENARIOS.f.clock).toBe("2026-09-24T10:12:00-05:00");
    for (const s of ["c", "d", "g"] as const)
      expect(TPL20_SCENARIOS[s].clock).toBe(TPL20_SCENARIOS.a.clock);
    render(wrap(<Tpl20Artboard params={{ st: "e", frame: true, static: true }} />));
    const art = document.querySelector("[data-artboard]");
    expect(art?.getAttribute("data-artboard")).toBe("e");
    expect(art?.getAttribute("data-clock")).toBe("2026-10-01T16:30:00-05:00");
    expect(art?.getAttribute("data-persona")).toBe("cole-hart");
  });

  it("figures come from the seed: strata (24) 3,286,400 and (16) 412,300, no '$' in cells", () => {
    const [s1, s2] = tpl20Sections("a");
    expect(s1).toMatchObject({ count: 24, total: "3,286,400" });
    expect(s2).toMatchObject({ count: 16, total: "412,300" });
    for (const r of tpl20Rows("a")) {
      for (const c of Object.values(r.cells)) expect(c.value).not.toContain("$");
    }
    expect(tpl20Rows("a")).toHaveLength(SURL_SHEET.rows.length);
  });
});

describe("TPL-20: states", () => {
  it("a: 40 rows · 1 exception, 0 adopted, every conclusion suggested, Simone on SURL-12", () => {
    board("a");
    expect(statusBar()).toContain("40 rows · 1 exception");
    expect(statusBar()).toContain("0 adopted");
    expect(tpl20Rows("a").every((r) => r.cells.conclusion?.state === "suggested")).toBe(true);
    expect(document.querySelector('[data-presence-row="SURL-12"]')?.textContent).toContain(
      "Simone Baptiste",
    );
    expect(statusBar()).toContain("Mon Sep 28, 5:00 PM");
  });

  it("b: the agent column runs on two rows, 38 of 40 evidence, screening flag", () => {
    board("b");
    expect(statusBar()).toContain("Agent column running");
    expect(statusBar()).toContain("38 of 40 evidence");
    expect(document.querySelector("[data-screening]")?.textContent).toBe(
      "Screening flag · Granite Rock Logistics",
    );
    expect(statusBar()).toContain("Sun Sep 27, 6:20 PM");
    expect(statusBar()).toContain("40 rows · 1 exception");
  });

  it("c: the SURL-05 drawer on Agents, Improperly excluded with 2 citations and person actions", () => {
    const { onIntent } = board("c");
    const drawer = screen.getByRole("dialog");
    expect(
      within(drawer).getAllByText("SURL-05 · Front Range Freight Co.").length,
    ).toBeGreaterThan(0);
    expect(within(drawer).getByText("Improperly excluded")).toBeTruthy();
    expect(within(drawer).getAllByRole("listitem")).toHaveLength(2);
    for (const name of ["Adopt", "Edit", "Raise exception…", "Expand testing"]) {
      expect(within(drawer).getByRole("button", { name })).toBeTruthy();
    }
    fireEvent.click(within(drawer).getByRole("button", { name: "Adopt" }));
    expect(onIntent).toHaveBeenCalledWith("adopt");
  });

  it("d: the Exceptions view shows SURL-05 alone and stratum 2 collapsed (0)", () => {
    board("d");
    const rows = tpl20Rows("d");
    expect(rows.map((r) => r.key)).toEqual(["SURL-05"]);
    expect(tpl20Sections("d").map((s) => s.count)).toEqual([1, 0]);
    expect(statusBar()).toContain("40 rows · 1 exception · View: Exceptions");
  });

  it("e: P CH · R HL on every row, every row locked, Signed off", () => {
    const { open } = board("e");
    const rows = tpl20Rows("e");
    expect(rows.every((r) => r.locked)).toBe(true);
    const signed = tpl20SignOffs("e");
    for (const r of rows) {
      expect(signed[r.key]?.P?.initials).toBe("CH");
      expect(signed[r.key]?.R?.initials).toBe("HL");
    }
    expect(screen.getAllByText("Signed off").length).toBeGreaterThan(0);
    expect(statusBar()).toContain("Thu Oct 1, 4:30 PM");
    const [first] = screen.getAllByRole("button", { name: "Hannah Leclerc, R: open sign-off" });
    expect(
      screen.getAllByRole("button", { name: "Hannah Leclerc, R: open sign-off" }),
    ).toHaveLength(14);
    if (first === undefined) throw new Error("no R chip");
    fireEvent.click(first);
    expect(open).toHaveBeenCalledWith(["SURL-01"], "R");
  });

  it("f: empty from template at Thu Sep 24, 10:12 AM", () => {
    board("f");
    expect(screen.getByText("No rows yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add row" })).toBeTruthy();
    expect(statusBar()).toContain("Thu Sep 24, 10:12 AM");
  });

  it("g: the Agents dock open on the auto-started run, canvas in cockpit", () => {
    board("g");
    expect(document.querySelector("[data-dock-run]")?.textContent).toBe(
      "Unrecorded liabilities tester · auto-started by trigger",
    );
    expect(document.querySelector('[data-sheet-layout="cockpit"]')).not.toBeNull();
  });

  it("no human-only verb renders on an agent element", () => {
    board("c");
    for (const el of document.querySelectorAll('[data-col-key="conclusion"] button')) {
      expect(el.textContent).not.toMatch(/\b(Approve|Sign off|Release|Send|Post|Decide)\b/);
    }
  });
});
