// KNW-01 · Knowledge library (K-01-T04). One test per artboard a–f on its fixture scenario, with
// the 48-item footings, the counting rule, the staff view (capabilities, and the API leaving drafts
// out) and the search mark (never the source-tracing purple). Axe runs in e2e/screens (not run in
// this lane, recorded in TASK-1434).
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { KNW01 } from ".";
import { type Knw01State, OPENS, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Knw01State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <KNW01 initial={OPENS[state]} />
    </QueryClientProvider>,
  );
}

function cards(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("[data-catalog-card]")];
}

function cardTitles(): string[] {
  return cards().map((c) => c.querySelector("p[title]")?.getAttribute("title") ?? "");
}

/** The CategoryList as label → count (undefined: no count). */
function categoryCounts(): Record<string, number | undefined> {
  const out: Record<string, number | undefined> = {};
  const list = screen.getByRole("listbox", { name: "Categories" });
  for (const option of within(list).getAllByRole("option")) {
    const count = option.querySelector("[data-count]")?.textContent;
    const label = option.querySelector("span span")?.textContent ?? "";
    out[label] = count == null ? undefined : Number(count);
  }
  return out;
}

async function loaded(): Promise<void> {
  await waitFor(() => {
    expect(document.querySelector("[data-catalog-grid][aria-busy='true']")).toBeNull();
    expect(cards().length).toBeGreaterThan(0);
  });
}

describe("KNW-01 a (Margaret Okonkwo, All)", () => {
  it("foots All 48 = 4 + 12 + 12 + 6 + 14, with no count on the five R2 categories", async () => {
    show("a");
    await loaded();
    await waitFor(() => {
      expect(categoryCounts()).toEqual({
        All: 48,
        "Engagement templates": undefined,
        Methodology: 4,
        Frameworks: undefined,
        "Firm standards": 12,
        Skills: undefined,
        Notes: undefined,
        Templates: 12,
        "Research & positions": 6,
        "Content packs": undefined,
        "Agent instructions": 14,
      });
    });
    expect(cards()).toHaveLength(48);
  });

  it("opens on cards 1, 2, 3, 5, 6, 7, 17, 29, 31 and the status picker reads 46 · 1 · 1", async () => {
    show("a");
    await loaded();
    expect(cardTitles().slice(0, 9)).toEqual([
      "BH Audit Methodology · EBP",
      "BH Audit Methodology · FS",
      "BH SSARS Methodology · Review, Compilation & Preparation",
      "1065 Review Checklist",
      "1040 Review Checklist",
      "BH AJE thresholds",
      "Engagement letter · EBP audit (§103(a)(3)(C))",
      "§754 election — Ridgeline transfer to Pell Street II LLC",
      "De minimis safe harbor and repairs vs improvements ($2,500)",
    ]);
    const pills = cards().map((c) => c.getAttribute("aria-label")?.split(", ").pop());
    expect(pills.filter((p) => p === "Published")).toHaveLength(46);
    expect(pills.filter((p) => p === "Draft")).toHaveLength(1);
    expect(pills.filter((p) => p === "Superseded")).toHaveLength(1);
    expect(screen.getAllByText("Used by 14 engagements").length).toBeGreaterThan(0);
    expect(screen.getByText("Applied to 162 returns")).toBeTruthy();
  });

  it("shows the + menu to whoever may manage or approve content, and the review queue count", async () => {
    show("a");
    await loaded();
    expect(screen.getByRole("button", { name: "Add to knowledge" })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Review queue/u }).textContent).toContain("2");
    });
  });
});

describe("KNW-01 b–f", () => {
  it("b: Methodology shows cards 1–4; card 4 struck, Superseded, kept for archived engagements", async () => {
    show("b");
    await loaded();
    expect(cards()).toHaveLength(4);
    const fourth = cards()[3];
    expect(fourth?.getAttribute("aria-label")).toBe("BH Audit Methodology · EBP, Superseded");
    expect(fourth?.querySelector("p[title]")?.className).toContain("line-through");
    expect(
      within(fourth ?? document.body).getByText("Kept for engagements archived under it."),
    ).toBeTruthy();
  });

  it("c: the review queue lists the 1040 Review Checklist v7 and the §754 memo", async () => {
    show("c");
    const rows = await waitFor(() => {
      const found = document.querySelectorAll("[data-review-row]");
      expect(found).toHaveLength(2);
      return [...found].map((r) => r.textContent);
    });
    expect(rows[0]).toContain("1040 Review Checklist v7 (TY2026)");
    expect(rows[0]).toContain("Daniel Reyes · submitted Sep 10");
    expect(rows[1]).toContain("§754 election — Ridgeline");
  });

  it("d: the change log names the person, newest last, and never the agent as approver", async () => {
    show("d");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-change]")).toHaveLength(4);
    });
    const lines = [...document.querySelectorAll("[data-change]")].map((r) => r.textContent);
    expect(lines[0]).toContain(
      "BH Audit Methodology · EBP v3 approved by Margaret Okonkwo · effective Jan 1, 2026",
    );
    expect(lines[3]).toContain("Request Chaser v3 available (Accrued)");
    expect(lines.join(" ")).not.toMatch(/approved by Accrued Agent/u);
  });

  it("e: Ana Cruz sees no + menu and no drafts; the API left them out", async () => {
    show("e");
    await loaded();
    expect(screen.queryByRole("button", { name: "Add to knowledge" })).toBeNull();
    expect(cards()).toHaveLength(47);
    expect(cards().some((c) => c.getAttribute("aria-label")?.endsWith("Draft") === true)).toBe(
      false,
    );
  });

  it("f: materiality finds cards 8 and 1; the mark is --nested, never the match purple", async () => {
    show("f");
    await waitFor(() => {
      expect(cardTitles()).toEqual(["Materiality ranges", "BH Audit Methodology · EBP"]);
    });
    const marks = document.querySelectorAll("[data-search-hit]");
    expect(marks).toHaveLength(1);
    expect(marks[0]?.textContent).toBe("Materiality");
    expect(marks[0]?.className).toContain("bg-nested");
    expect(document.body.innerHTML).not.toMatch(/match-/u);
  });

  it("every state renders", async () => {
    for (const state of STATES) {
      show(state);
      await waitFor(() => {
        expect(screen.getByRole("tablist", { name: "Knowledge" })).toBeTruthy();
      });
      cleanup();
      restore?.();
      restore = undefined;
    }
  });
});

describe("KNW-01 avoid", () => {
  it("no publishing control for anyone, no 600/700 weight, no blue", async () => {
    show("a");
    await loaded();
    expect(screen.queryByRole("button", { name: /^(Publish|Approve)/u })).toBeNull();
    expect(document.body.innerHTML).not.toMatch(/font-(semibold|bold)|blue-/u);
  });
});
