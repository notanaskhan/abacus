// ENG-01 · Engagements index (P-07-T27). One test per artboard (a–e) on its fixture scenario, the
// spec's acceptance checklist, P-07 Story 6.1 (tiles and segments foot to the header in every
// scenario), the error state, tile and segment filtering, and the route behind `engagements.v2`.
// "Scenarios a to e pass with axe" is e2e/screens/ENG-01.spec.ts.
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
import { DEFAULT_ENGAGEMENT_FILTERS, type EngagementFilters } from "../../domain/engagements";
import { engagementsIndexRoute } from "../../routes/firm/areas";
import { newQueryClient } from "../../testing/support";
import { ENG01 } from ".";
import { type Eng01State, SEARCH, STATES, scenarios } from "./scenarios";

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

function Harness({ initial }: { initial: EngagementFilters }): JSX.Element {
  const [filters, setFilters] = useState(initial);
  return <ENG01 filters={filters} onFilters={setFilters} />;
}

function show(state: Eng01State, scenario: Scenario = scenarios[state]): Seen {
  const seen = install(scenario);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Harness initial={{ ...DEFAULT_ENGAGEMENT_FILTERS, ...SEARCH[state] }} />
    </QueryClientProvider>,
  );
  return seen;
}

function rows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("tr[data-row]")];
}

const COL = {
  engagement: 0,
  client: 1,
  type: 2,
  period: 3,
  office: 4,
  partner: 5,
  status: 6,
  work: 7,
  letter: 8,
  due: 9,
} as const;

function cell(row: HTMLElement, index: number): string {
  return row.querySelectorAll("td")[index]?.textContent ?? "";
}

function clients(): string[] {
  return rows().map((r) => cell(r, COL.client));
}

/** The seven tiles' labels, in order. */
function tileLabels(): string[] {
  return [...document.querySelectorAll<HTMLElement>("[data-tile]")].map(
    (t) => t.dataset.tile ?? "",
  );
}

function tileCount(label: string): number {
  const tile = document.querySelector<HTMLElement>(`[data-tile='${label}']`);
  const text = tile?.querySelector("span")?.textContent ?? "";
  return Number(text.replace(/,/g, ""));
}

const TILE_WORDS = [
  "Prospect",
  "Accepted",
  "Letter signed",
  "Active",
  "On hold",
  "Delivered",
  "Archived",
];

function tileSum(): number {
  return TILE_WORDS.reduce((sum, w) => sum + tileCount(w), 0);
}

/** The segment counts, as label → n ("All 275", "Tax 224", …). */
function segments(): Record<string, number> {
  const list = screen.getByRole("tablist", { name: "Service line" });
  const out: Record<string, number> = {};
  for (const tab of within(list).getAllByRole("tab")) {
    const text = tab.textContent;
    const m = /^(\D+?)\s*([\d,]+)$/u.exec(text.trim());
    if (m?.[1] !== undefined && m[2] !== undefined)
      out[m[1].trim()] = Number(m[2].replace(/,/g, ""));
  }
  return out;
}

const ROW_CLIENTS = [
  "Copperleaf Coffee Roasters, Inc.",
  "Bluebird Bakery Co.",
  "Ridgeline Property Partners, LP",
  "Ridgeline Property Partners, LP",
  "Harborview Dental Properties, LP",
  "Granite Peak Outdoor Supply, Inc.",
  "Fairhaven Foods 401(k) Plan",
  "Marcus & Dana Whitley",
  "Bluestem Analytics, LLC",
  "Calloway Family Trust",
  "Northwind Robotics, Inc.",
  "Jonah & Claire Feld",
  "Meera Shah",
  "Estate of Walter Thornbury",
  "Lakeshore Literacy Alliance",
  "Estate of Walter Thornbury",
];

describe("ENG-01 artboards", () => {
  it("has a scenario for every artboard a–e, all Margaret Okonkwo at E0", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e"]);
    for (const s of STATES) {
      expect(scenarios[s].persona).toBe("margaret-okonkwo");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
  });

  it("ENG-01a default (Period │ Current, DEC-343): 273 engagements, the 16 rows past due first, the summary line", async () => {
    show("a");
    expect(await screen.findByText("Showing 16 of 273")).toBeTruthy();
    expect(clients()).toEqual(ROW_CLIENTS);
    expect(
      screen.getByText("273 engagements · 1 prospect · 4 awaiting a signed letter · 2 past due"),
    ).toBeTruthy();
    const first = rows()[0];
    if (first === undefined) throw new Error("no rows");
    expect(cell(first, COL.engagement)).toBe("2026 Close");
    expect(cell(first, COL.type)).toBe("CAS · Monthly close");
    expect(cell(first, COL.period)).toBe("Jan–Dec 2026");
    expect(cell(first, COL.office)).toBe("Denver");
    expect(cell(first, COL.partner)).toBe("PR");
    expect(cell(first, COL.status)).toBe("Active");
    expect(cell(first, COL.work)).toBe("12 closes7 delivered · Aug in progress");
    expect(cell(first, COL.letter)).toBe("✓ Signed Mar 3");
    expect(cell(first, COL.due)).toBe("Sep 10Aug close · 4 days past due");
    // No banner, no Clear in the default view.
    expect(document.querySelector("[data-list='banner']")).toBeNull();
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
  });

  it("ENG-01b Letter │ Not signed with Accepted: rows 4, 6, 7, 9 and the G3 banner", async () => {
    const seen = show("b");
    expect(await screen.findByText("Showing 4 of 4")).toBeTruthy();
    expect(rows().map((r) => cell(r, COL.engagement))).toEqual([
      "Cost segregation & §754 analysis",
      "FY2026 FS Audit",
      "PY2025 EBP Audit",
      "2026 Close (from Oct)",
    ]);
    expect(rows().map((r) => cell(r, COL.letter))).toEqual([
      "Sent Sep 14 · 0 of 2",
      "1 of 2 signed",
      "Sent Sep 8 · 0 of 2",
      "Viewed Sep 11 · 0 of 2",
    ]);
    // The Prospect estate engagement has no letter yet and stays out of this filter.
    expect(clients()).not.toContain("Estate of Walter Thornbury");
    expect(
      screen.getByText("Portal requests and billing stay held until the letter is signed (G3)."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Letter: Not signed" })).toBeTruthy();
    const accepted = document.querySelector<HTMLElement>("[data-tile='Accepted']");
    expect(accepted?.getAttribute("aria-pressed")).toBe("true");
    expect(seen.calls.some((c) => c.query.includes("letter=not_signed"))).toBe(true);
    expect(seen.calls.some((c) => c.query.includes("tile=accepted"))).toBe(true);
  });

  it("ENG-01c Advisory: the Ridgeline project; the tiles recount to Accepted 1, others 0", async () => {
    show("c");
    expect(await screen.findByText("Showing 1 of 1")).toBeTruthy();
    expect(rows().map((r) => cell(r, COL.engagement))).toEqual([
      "Cost segregation & §754 analysis",
    ]);
    const row = rows()[0];
    if (row === undefined) throw new Error("no row");
    expect(cell(row, COL.type)).toBe("Advisory · Project");
    expect(cell(row, COL.work)).toBe("1 projectScoping");
    expect(cell(row, COL.due)).toBe("Sep 15§754 election deadline");
    for (const word of TILE_WORDS) expect(tileCount(word)).toBe(word === "Accepted" ? 1 : 0);
  });

  it("ENG-01d Harbor Lane: No engagements match 'Harbor Lane'. and Clear filters", async () => {
    show("d");
    expect(await screen.findByText("No engagements match 'Harbor Lane'.")).toBeTruthy();
    fireEvent.click(screen.getByText("Clear filters"));
    expect(await screen.findByText("Showing 16 of 273")).toBeTruthy();
  });

  it("ENG-01e loading: skeleton tile counts and 8 skeleton rows; no count or summary", async () => {
    show("e");
    expect(screen.getByRole("heading", { name: "Engagements" })).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelectorAll("[data-skeleton] [data-row]").length).toBe(8);
    });
    expect(document.querySelectorAll("[data-tile-count='pending']").length).toBe(7);
    expect(screen.queryByText(/engagements ·/)).toBeNull();
    expect(screen.queryByText(/^Showing/)).toBeNull();
  });

  it("error: the C-20 error row with Retry", async () => {
    show("a", {
      ...scenarios.a,
      handlers: { ...scenarios.a.handlers, "GET /v1/engagements/index": () => json({}, 500) },
    });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });
});

describe("ENG-01 acceptance", () => {
  it("ENG-01 acceptance: segment counts foot: 224 + 25 + 23 + 1 = 273 (DEC-343)", async () => {
    show("a");
    await screen.findByText("Showing 16 of 273");
    expect(segments()).toEqual({ All: 273, Tax: 224, Audit: 25, CAS: 23, Advisory: 1 });
  });

  it("ENG-01 acceptance: the seven tiles sum to 273 (1 + 4 + 0 + 128 + 0 + 140 + 0); Accepted 4 is the letters out, Prospect 1 the estate", async () => {
    show("a");
    await screen.findByText("Showing 16 of 273");
    expect(TILE_WORDS.map(tileCount)).toEqual([1, 4, 0, 128, 0, 140, 0]);
    expect(tileSum()).toBe(273);
    expect(tileLabels()).toEqual(TILE_WORDS);
    fireEvent.click(screen.getByRole("button", { name: /Prospect/ }));
    expect(await screen.findByText("Showing 1 of 1")).toBeTruthy();
    expect(rows().map((r) => cell(r, COL.engagement))).toEqual([
      "Estate returns — final 1040 · 1041 · 706",
    ]);
  });

  it("ENG-01 acceptance: status words come only from §3.3.1; sub-lines use the work item's own words", async () => {
    show("a");
    await screen.findByText("Showing 16 of 273");
    const words = new Set(rows().map((r) => cell(r, COL.status)));
    for (const w of words)
      expect(["Prospect", "Accepted", "Active", "Delivered", "Archived"]).toContain(w);
    expect(rows().map((r) => cell(r, COL.work))).toEqual(
      expect.arrayContaining([
        "1 returnIn review · Partner",
        "1 projectScoping",
        "1 auditPlanningProcessing",
      ]),
    );
  });

  it("ENG-01 acceptance: days to deadline: red ≤ 7, amber ≤ 30, ink-2 beyond; Copperleaf 4 and Bluebird 2 days past due", async () => {
    show("a");
    await screen.findByText("Showing 16 of 273");
    const due = rows().map((r) => r.querySelectorAll("td")[COL.due]?.querySelector("[data-due]"));
    const at = (i: number): [string, string] => [
      due[i]?.textContent ?? "",
      due[i]?.getAttribute("data-due") ?? "",
    ];
    expect(at(0)).toEqual(["Aug close · 4 days past due", "past"]);
    expect(at(1)).toEqual(["Aug close · 2 days past due", "past"]);
    expect(at(2)).toEqual(["1 day", "red"]);
    expect(at(9)).toEqual(["16 days", "amber"]);
    expect(at(11)).toEqual(["31 days", "ink"]);
    expect(at(12)).toEqual(["31 days", "ink"]);
    expect(at(13)).toEqual(["31 days", "ink"]);
  });

  it("DEC-343 (ED-027): Period │ All counts the two archived audits under Archived (275); Juniper & Oak's archived row has no next due", async () => {
    show("a", scenarios.a);
    await screen.findByText("Showing 16 of 273");
    expect(tileCount("Archived")).toBe(0);
    expect(clients()).not.toContain("Juniper & Oak Interiors, LLC");
    cleanup();
    restore?.();
    restore = undefined;
    install(scenarios.a);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Harness initial={{ ...DEFAULT_ENGAGEMENT_FILTERS, period: "all" }} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Showing 17 of 275")).toBeTruthy();
    expect(tileCount("Archived")).toBe(2);
    expect(tileSum()).toBe(275);
    expect(segments()).toEqual({ All: 275, Tax: 224, Audit: 27, CAS: 23, Advisory: 1 });
    const last = rows()[16];
    if (last === undefined) throw new Error("no archived row");
    expect(cell(last, COL.client)).toBe("Juniper & Oak Interiors, LLC");
    expect(cell(last, COL.status)).toBe("Archived");
    expect(cell(last, COL.due)).toBe("—");
  });

  it("ENG-01 acceptance: one pane with a centred title; rows hairline-separated, no zebra", async () => {
    show("a");
    await screen.findByText("Showing 16 of 273");
    expect(screen.getByRole("heading", { name: "Engagements" })).toBeTruthy();
    const classes = rows().map((r) => r.className);
    expect(classes.every((c) => c.includes("border-hair"))).toBe(true);
    expect(classes.some((c) => /odd:|even:/.test(c))).toBe(false);
  });

  it("ENG-01 acceptance: no Active engagement lacks a signed letter; the unsigned are Accepted, but the Prospect estate shows — and no work item", async () => {
    show("a");
    await screen.findByText("Showing 16 of 273");
    for (const r of rows()) {
      const word = cell(r, COL.status);
      const letter = cell(r, COL.letter);
      if (word === "Active") expect(letter.startsWith("✓ Signed")).toBe(true);
      if (!letter.startsWith("✓ Signed")) expect(["Accepted", "Prospect"]).toContain(word);
    }
    const estate = rows()[15];
    if (estate === undefined) throw new Error("no estate row");
    expect(cell(estate, COL.status)).toBe("Prospect");
    expect(cell(estate, COL.letter)).toBe("—");
    expect(cell(estate, COL.work).startsWith("—")).toBe(true);
  });

  it("P-07 Story 6.1: the tiles and segments sum to the header in every scenario", async () => {
    for (const state of ["a", "b", "c"] as const) {
      show(state);
      const page = await screen.findByText(/^Showing \d+ of [\d,]+$/u);
      const total = Number(/of ([\d,]+)$/u.exec(page.textContent)?.[1]?.replace(/,/g, ""));
      // A tile filters the rows; the tiles count without it, so they foot to the list without
      // the tile (b: the four Accepted with letters out are the whole Letter │ Not signed list).
      expect(tileSum()).toBe(total);
      const seg = segments();
      expect((seg.Tax ?? 0) + (seg.Audit ?? 0) + (seg.CAS ?? 0) + (seg.Advisory ?? 0)).toBe(
        seg.All,
      );
      cleanup();
      restore?.();
      restore = undefined;
    }
  });
});

describe("ENG-01 behaviour", () => {
  it("a tile toggles the status filter, and the counts stay the counts without it", async () => {
    const seen = show("a");
    await screen.findByText("Showing 16 of 273");
    fireEvent.click(screen.getByRole("button", { name: /Accepted/ }));
    expect(await screen.findByText("Showing 4 of 4")).toBeTruthy();
    expect(tileSum()).toBe(273);
    expect(seen.calls.some((c) => c.query.includes("tile=accepted"))).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /Accepted/ }));
    expect(await screen.findByText("Showing 16 of 273")).toBeTruthy();
  });

  it("a segment is sent as service_line and recounts the tiles", async () => {
    const seen = show("a");
    await screen.findByText("Showing 16 of 273");
    fireEvent.click(screen.getByRole("tab", { name: /^Audit/ }));
    expect(await screen.findByText("Showing 4 of 25")).toBeTruthy();
    expect(tileSum()).toBe(25);
    expect(seen.calls.some((c) => c.query.includes("service_line=audit"))).toBe(true);
  });

  it("the search is sent as q and narrows the rows", async () => {
    const seen = show("a");
    await screen.findByText("Showing 16 of 273");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Ridgeline" } });
    expect(await screen.findByText("Showing 2 of 2")).toBeTruthy();
    expect(seen.calls.some((c) => c.query.includes("q=Ridgeline"))).toBe(true);
  });

  it("partner cells are initials with the partner's name as their tooltip", async () => {
    show("a");
    await screen.findByText("Showing 16 of 273");
    await waitFor(() => {
      expect(rows()[0]?.querySelector("abbr")?.getAttribute("title")).toBe("Priya Raman");
    });
  });

  it("a row opens its engagement record (ENG-02)", async () => {
    install(scenarios.a);
    const opened: string[] = [];
    render(
      <QueryClientProvider client={newQueryClient()}>
        <ENG01
          filters={DEFAULT_ENGAGEMENT_FILTERS}
          onFilters={() => undefined}
          onOpen={(id) => opened.push(id)}
        />
      </QueryClientProvider>,
    );
    await screen.findByText("Showing 16 of 273");
    const first = rows()[0];
    if (first === undefined) throw new Error("no row");
    fireEvent.click(first);
    expect(opened).toEqual([first.dataset.row]);
  });

  it("Export is hidden (cut) and no control is an agent-owned send, approve or sign-off", async () => {
    show("a");
    await screen.findByText("Showing 16 of 273");
    expect(screen.queryByRole("button", { name: /Export/ })).toBeNull();
    for (const word of [/^Approve/, /^Sign off/, /^Release/, /^Send/, /^Post/, /^Decide/]) {
      expect(screen.queryByRole("button", { name: word })).toBeNull();
    }
  });
});

describe("ENG-01 route /engagements", () => {
  it("flag on (engagements.v2): ENG-01", async () => {
    install(scenarios.a);
    const Page = engagementsIndexRoute.options.component as () => JSX.Element;
    render(
      <QueryClientProvider client={newQueryClient()}>
        <Page />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Showing 16 of 273")).toBeTruthy();
    expect(document.querySelector("[data-screen='ENG-01']")).not.toBeNull();
  });
});
