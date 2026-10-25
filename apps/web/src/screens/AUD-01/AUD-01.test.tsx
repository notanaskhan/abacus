// AUD-01 · Audits index (A-01-T11). One test per artboard (a–h) on its fixture scenario, the
// revision acceptance checklist, A-01 Stories 1.1–1.4 (tiles, segments and caption foot in every
// scenario; a walled user's totals foot without the hidden rows), the error state and the AVOID
// list. i (Board) is K-04's. "Scenarios pass axe" is e2e/screens (A-01-T28).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { type AuditFilters, DEFAULT_AUDIT_FILTERS } from "../../domain/audits";
import { auditHandlers } from "../../fixtures/handlers/audits";
import { getSeed } from "../../fixtures/seed";
import { stableId } from "../../fixtures/seed/prng";
import { auditsRoute } from "../../routes/firm/audits";
import { newQueryClient, renderRoutes } from "../../testing/support";
import { AUD01 } from ".";
import { type Aud01State, SEARCH, STATES, scenarios } from "./scenarios";

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

function install(scenario: Scenario, persona?: string): Seen {
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
  restore = installFixtureMode(
    { ...scenario, handlers },
    persona === undefined ? {} : { persona },
  );
  return seen;
}

function Harness({ initial }: { initial: AuditFilters }): JSX.Element {
  const [filters, setFilters] = useState(initial);
  return <AUD01 filters={filters} onFilters={setFilters} />;
}

function show(state: Aud01State, scenario: Scenario = scenarios[state], persona?: string): Seen {
  const seen = install(scenario, persona);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Harness initial={{ ...DEFAULT_AUDIT_FILTERS, ...SEARCH[state] }} />
    </QueryClientProvider>,
  );
  return seen;
}

function rows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("tr[data-row]")];
}

const COL = {
  engagement: 0,
  type: 1,
  period: 2,
  phase: 3,
  pbc: 4,
  epMgr: 5,
  office: 6,
  due: 7,
  archive: 8,
} as const;

function cell(row: HTMLElement | undefined, index: number): string {
  return row?.querySelectorAll("td")[index]?.textContent ?? "";
}

function names(): string[] {
  return rows().map((r) => cell(r, COL.engagement));
}

function rowOf(name: string): HTMLElement | undefined {
  return rows().find((r) => cell(r, COL.engagement) === name);
}

const TILE_WORDS = ["Planning", "Fieldwork", "In review", "Ready to release", "Released"];

function tileCount(label: string): number {
  const tile = document.querySelector<HTMLElement>(`[data-tile='${label}']`);
  const text = tile?.querySelector("span")?.textContent ?? "";
  return Number(text.replace(/,/g, ""));
}

function tiles(): number[] {
  return TILE_WORDS.map(tileCount);
}

/** The segment tabs as label → count (undefined: no badge). */
function segments(): Record<string, number | undefined> {
  const list = screen.getByRole("tablist", { name: "Audit segments" });
  const out: Record<string, number | undefined> = {};
  for (const tab of within(list).getAllByRole("tab")) {
    const text = tab.textContent.trim();
    const m = /^(\D+?)\s*([\d,]+)?$/u.exec(text);
    if (m?.[1] !== undefined) out[m[1].trim()] = m[2] === undefined ? undefined : Number(m[2]);
  }
  return out;
}

function groups(): string[] {
  return [...document.querySelectorAll<HTMLElement>("th[scope='rowgroup']")].map(
    (g) => g.textContent,
  );
}

const A_NAMES = [
  "Fairhaven Foods 401(k) Plan",
  "Northwind Robotics 401(k) Plan",
  "Tamarack Health System 403(b) Plan",
  "Granite Peak Outdoor Supply, Inc.",
  "Halcyon Foods Distribution, Inc.",
  "Larimer Cooperative Grocery",
  "Riverbend Community Theater",
];

describe("AUD-01 artboards", () => {
  it("has a scenario for every artboard a–h, all Hannah Leclerc; a–f at 9:41, g–h at 10:30", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "h"]);
    for (const s of STATES) expect(scenarios[s].persona).toBe("hannah-leclerc");
    for (const s of ["a", "b", "c", "d", "e", "f"] as const) {
      expect(scenarios[s].clock).toBe("2026-09-14T09:41:00-05:00");
    }
    for (const s of ["g", "h"] as const)
      expect(scenarios[s].clock).toBe("2026-09-14T10:30:00-05:00");
  });

  it("AUD-01a default: 27 audits by phase then report due, the caption and the segments", async () => {
    show("a");
    expect(await screen.findByText("Showing 27 of 27")).toBeTruthy();
    expect(tiles()).toEqual([7, 9, 6, 2, 3]);
    expect(
      screen.getByText(
        "27 engagements · EBP 14 · FS audit 6 · Review 4 · Compilation/preparation 3",
      ),
    ).toBeTruthy();
    expect(segments()).toEqual({
      All: 27,
      "Financial statement": 6,
      EBP: 14,
      "Review & compilation": 7,
      "SOC & IT": undefined,
      "Internal audit": undefined,
    });
    expect(groups()).toEqual([
      "Planning · 7",
      "Fieldwork · 9",
      "In review · 6",
      "Ready to release · 2",
      "Released · 3",
    ]);
    expect(names().slice(0, 7)).toEqual(A_NAMES);
    // Released rows carry no report due; the server breaks the tie by name.
    expect(names().slice(-3)).toEqual([
      "Bayside Electric Cooperative 401(k) Plan",
      "Juniper & Oak Interiors, LLC",
      "Meridian Tool & Die, Inc.",
    ]);
    expect(screen.getByRole("heading", { name: "Audits" })).toBeTruthy();
    // No ViewToggle until K-04 registers C14 (i deferred).
    expect(screen.queryByRole("tab", { name: "Board" })).toBeNull();
  });

  it("AUD-01b Ready to release: Cobalt Ridge and Halden Health, Showing 2 of 27, tiles keep their counts", async () => {
    const seen = show("b");
    expect(await screen.findByText("Showing 2 of 27")).toBeTruthy();
    expect(names()).toEqual([
      "Cobalt Ridge Manufacturing 401(k) Plan",
      "Halden Health 403(b) Plan",
    ]);
    expect(tiles()).toEqual([7, 9, 6, 2, 3]);
    const tile = document.querySelector<HTMLElement>("[data-tile='Ready to release']");
    expect(tile?.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: /Phase.*Ready to release/ })).toBeTruthy();
    expect(seen.calls.some((c) => c.query.includes("phase=ready_to_release"))).toBe(true);
  });

  it("AUD-01c Report due │ Next 14 days: Sep 18, 21, 25, 28 (Fenwick Sep 30 excluded)", async () => {
    const seen = show("c");
    expect(await screen.findByText("Showing 4 of 4")).toBeTruthy();
    // Grouped by phase first: In review (Kettle & Kiln, Oakline), then Ready to release.
    expect(rows().map((r) => r.querySelector("[data-due]")?.firstChild?.textContent)).toEqual([
      "Sep 25",
      "Sep 28",
      "Sep 18",
      "Sep 21",
    ]);
    expect(names()).not.toContain("Fenwick Family Foundation");
    expect(screen.getByRole("button", { name: /Report due.*Next 14 days/ })).toBeTruthy();
    expect(seen.calls.some((c) => c.query.includes("due=14d"))).toBe(true);
  });

  it("AUD-01d Northwind: Processing with a spinner, its popover on focus, 1 of 14 workpapers", async () => {
    show("d");
    await screen.findByText("Showing 27 of 27");
    const northwind = rowOf("Northwind Robotics 401(k) Plan");
    const pill = northwind?.querySelector<HTMLElement>("[data-phase='processing']");
    expect(pill?.textContent).toBe("Processing");
    expect(pill?.querySelector("[data-spin], svg")).toBeTruthy();
    expect(cell(northwind, COL.pbc)).toBe("11 of 24");
    expect(cell(northwind, COL.epMgr)).toBe("MO / HL");
    expect(cell(northwind, COL.due)).toContain("Oct 9");
    act(() => {
      pill?.focus();
    });
    const tip = await screen.findByRole("tooltip");
    expect(tip.textContent).toContain("Run 1 · started 9:24 AM by Marcus Delaney");
    expect(tip.textContent).toContain(
      "1 of 14 workpapers complete · blocked on a partner decision",
    );
  });

  it("AUD-01e Pinecrest: No results for 'Pinecrest'. and Clear filters resets every filter", async () => {
    show("e");
    expect(await screen.findByText("No results for 'Pinecrest'.")).toBeTruthy();
    fireEvent.click(screen.getByText("Clear filters"));
    expect(await screen.findByText("Showing 27 of 27")).toBeTruthy();
  });

  it("AUD-01f loading: 5 skeleton tiles and 8 skeleton rows; no count or caption", async () => {
    show("f");
    expect(screen.getByRole("heading", { name: "Audits" })).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelectorAll("[data-skeleton] [data-row]").length).toBe(8);
    });
    expect(document.querySelectorAll("[data-tile-count='pending']").length).toBe(5);
    expect(screen.queryByText(/engagements ·/)).toBeNull();
    expect(screen.queryByText(/^Showing/)).toBeNull();
  });

  it("AUD-01g wave 7: 33 rows; 10 + 11 + 6 + 2 + 4 and 7 + 14 + 7 + 3 + 2 both foot to 33", async () => {
    show("g");
    expect(await screen.findByText("Showing 33 of 33")).toBeTruthy();
    expect(tiles()).toEqual([10, 11, 6, 2, 4]);
    expect(tiles().reduce((a, b) => a + b, 0)).toBe(33);
    expect(segments()).toEqual({
      All: 33,
      "Financial statement": 7,
      EBP: 14,
      "Review & compilation": 7,
      "SOC & IT": 3,
      "Internal audit": 2,
    });
    expect(
      screen.getByText(
        "33 engagements · EBP 14 · FS audit 7 · Review 4 · Compilation/preparation 3 · SOC & IT 3 · Internal audit 2",
      ),
    ).toBeTruthy();
    // All six §9.10 rows in the right phase with EP CM, PR or MO as seeded.
    const six: [string, string, string][] = [
      ["Harlow & Pike Holdings, Inc.", "Planning", "MO / OH"],
      ["Larkfield Payroll Services", "Planning", "CM / LK"],
      ["Prairie Lakes Community Bank", "Planning", "PR / LK"],
      ["Tessellate Health Cloud, Inc.", "Fieldwork", "CM / LK"],
      ["Ashford Manufacturing Co.", "Fieldwork", "PR / LK"],
      ["Brightline Telehealth", "Released Aug 21", "CM / LK"],
    ];
    for (const [name, phase, ep] of six) {
      const row = rowOf(name);
      expect(cell(row, COL.phase).startsWith(phase)).toBe(true);
      expect(cell(row, COL.epMgr)).toBe(ep);
    }
    expect(cell(rowOf("Harlow & Pike Holdings, Inc."), COL.phase)).toContain("Component auditor");
    expect(cell(rowOf("Harlow & Pike Holdings, Inc."), COL.type)).toBe("FS audit (group)");
    expect(cell(rowOf("Tessellate Health Cloud, Inc."), COL.pbc)).toBe("186 of 212");
    expect(cell(rowOf("Tessellate Health Cloud, Inc."), COL.phase)).toContain("3 exceptions");
    expect(cell(rowOf("Ashford Manufacturing Co."), COL.phase)).toContain("9 issues · 2 overdue");
    // Brightline: released Aug 21 + 60 = Oct 20 → 36 days on Sep 14.
    expect(cell(rowOf("Brightline Telehealth"), COL.archive)).toBe("Archive in 36 days");
  });

  it("AUD-01h SOC & IT: Larkfield, Tessellate and Brightline", async () => {
    const seen = show("h");
    expect(await screen.findByText("Showing 3 of 3")).toBeTruthy();
    expect(names()).toEqual([
      "Larkfield Payroll Services",
      "Tessellate Health Cloud, Inc.",
      "Brightline Telehealth",
    ]);
    expect(seen.calls.some((c) => c.query.includes("segment=soc"))).toBe(true);
  });

  it("error: the C-20 error row with Retry", async () => {
    show("a", {
      ...scenarios.a,
      handlers: { ...scenarios.a.handlers, "GET /v1/audits": () => json({}, 500) },
    });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });
});

describe("AUD-01 acceptance", () => {
  it("AUD-01 acceptance: tiles read 7 · 9 · 6 · 2 · 3 and sum to 27; the caption's 14/6/4/3 match the Type column", async () => {
    show("a");
    await screen.findByText("Showing 27 of 27");
    expect(tiles().reduce((a, b) => a + b, 0)).toBe(27);
    const types = rows().map((r) => cell(r, COL.type));
    expect(types.filter((t) => t.startsWith("EBP")).length).toBe(14);
    expect(types.filter((t) => t === "FS audit").length).toBe(6);
    expect(types.filter((t) => t === "Review (AR-C 90)").length).toBe(4);
    expect(
      types.filter((t) => t === "Compilation (AR-C 80)" || t === "Preparation (AR-C 70)").length,
    ).toBe(3);
  });

  it("AUD-01 acceptance: Northwind reads EBP DC · §103(a)(3)(C) · PY2025 · 11 of 24 with its 40×3 bar · MO / HL · Chicago · Oct 9 · —", async () => {
    show("a");
    await screen.findByText("Showing 27 of 27");
    const row = rowOf("Northwind Robotics 401(k) Plan");
    expect(cell(row, COL.type)).toBe("EBP DC · §103(a)(3)(C)");
    expect(cell(row, COL.period)).toBe("PY2025");
    const bar = row?.querySelector("[role='progressbar']");
    expect(bar?.getAttribute("aria-valuenow")).toBe("11");
    expect(bar?.getAttribute("aria-valuemax")).toBe("24");
    expect(cell(row, COL.office)).toBe("Chicago");
    expect(cell(row, COL.archive)).toBe("—");
  });

  it("AUD-01 acceptance: Bayside's archive clock: released Jul 29 + 60 days = Sep 27 = Archive in 13 days on Sep 14", async () => {
    show("a");
    await screen.findByText("Showing 27 of 27");
    const row = rowOf("Bayside Electric Cooperative 401(k) Plan");
    expect(cell(row, COL.phase)).toBe("Released Jul 29");
    expect(row?.querySelector("[data-phase='released']")?.className).toContain("bg-green");
    expect(cell(row, COL.archive)).toBe("Archive in 13 days");
    expect(row?.querySelector("[data-archive='archiving']")?.className).toContain("bg-nested");
  });

  it("AUD-01 acceptance: Fairhaven shows no PBC count before G3 and the tag Letter sent Sep 8", async () => {
    show("a");
    await screen.findByText("Showing 27 of 27");
    const row = rowOf("Fairhaven Foods 401(k) Plan");
    expect(cell(row, COL.pbc)).toBe("—");
    expect(cell(row, COL.phase)).toBe("PlanningLetter sent Sep 8");
  });

  it("AUD-01 acceptance: status words from §3.3.1 only; Released solid green, Archived soon + lock", async () => {
    show("a");
    await screen.findByText("Showing 27 of 27");
    const words = new Set(rows().map((r) => r.querySelector("[data-phase]")?.textContent ?? ""));
    for (const w of words) {
      expect(
        ["Planning", "Processing", "Fieldwork", "In review", "Ready to release"].includes(w) ||
          /^Released [A-Z][a-z]{2} \d{1,2}$/u.test(w),
      ).toBe(true);
    }
    const meridian = rowOf("Meridian Tool & Die, Inc.");
    expect(cell(meridian, COL.archive)).toBe("Archived");
    expect(meridian?.querySelector("[data-archive='archived'] svg")).toBeTruthy();
  });

  it("AUD-01 acceptance: report due Sep 18 is red-ink 500, Sep 21 – Oct 13 amber-ink, later ink-2; each with hidden text", async () => {
    show("a");
    await screen.findByText("Showing 27 of 27");
    const due = (name: string) => rowOf(name)?.querySelector<HTMLElement>("[data-due]");
    expect(due("Cobalt Ridge Manufacturing 401(k) Plan")?.className).toContain("text-red-ink");
    expect(due("Cobalt Ridge Manufacturing 401(k) Plan")?.textContent).toBe(
      "Sep 18 due in 4 days",
    );
    expect(due("Halden Health 403(b) Plan")?.className).toContain("text-amber-ink");
    expect(due("Tamarack Health System 403(b) Plan")?.className).toContain("text-amber-ink");
    expect(due("Granite Peak Outdoor Supply, Inc.")?.className).toContain("text-ink-2");
  });

  it("AUD-01 acceptance: no $, no materiality figure and no severity on the index", async () => {
    show("a");
    await screen.findByText("Showing 27 of 27");
    const text = document.body.textContent;
    expect(text).not.toContain("$");
    expect(/materiality\D{0,12}\d/iu.test(text)).toBe(false);
    expect(/severity|material weakness|significant deficiency/iu.test(text)).toBe(false);
  });

  it("AUD-01 acceptance (R2): frames a–f keep 27 audits; the new segments appear without changing their rows", async () => {
    for (const state of ["a", "b", "c", "d"] as const) {
      show(state);
      const page = await screen.findByText(/^Showing \d+ of \d+$/u);
      expect(page.textContent).toMatch(/of (27|4)$/u);
      expect(segments()["SOC & IT"]).toBeUndefined();
      cleanup();
      restore?.();
      restore = undefined;
    }
  });

  it("A-01 Story 1.2: a tile toggles the phase filter and the tiles keep their counts", async () => {
    const seen = show("a");
    await screen.findByText("Showing 27 of 27");
    const tile = (): HTMLElement => {
      const el = document.querySelector<HTMLElement>("[data-tile='Fieldwork']");
      if (el === null) throw new Error("no Fieldwork tile");
      return el;
    };
    fireEvent.click(tile());
    expect(await screen.findByText("Showing 9 of 27")).toBeTruthy();
    expect(tiles()).toEqual([7, 9, 6, 2, 3]);
    expect(seen.calls.some((c) => c.query.includes("phase=fieldwork"))).toBe(true);
    fireEvent.click(tile());
    expect(await screen.findByText("Showing 27 of 27")).toBeTruthy();
  });

  it("A-01 Story 1.2: a segment is sent as segment and recounts tiles and caption", async () => {
    const seen = show("a");
    await screen.findByText("Showing 27 of 27");
    fireEvent.click(screen.getByRole("tab", { name: /^EBP/ }));
    expect(await screen.findByText("Showing 14 of 14")).toBeTruthy();
    expect(tiles().reduce((a, b) => a + b, 0)).toBe(14);
    expect(seen.calls.some((c) => c.query.includes("segment=ebp"))).toBe(true);
  });

  it("A-01 Story 1.4: a walled user's rows, tiles, segments and caption foot to 25 without Granite Peak", async () => {
    const seed = getSeed();
    const granite = stableId("client:granite-peak");
    const walled = {
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        ...auditHandlers({
          ...seed,
          walls: [
            ...seed.walls,
            {
              clientId:
                seed.engagements.find((e) => e.client_name.startsWith("Granite Peak"))
                  ?.client_id ?? granite,
              clientName: "Granite Peak Outdoor Supply, Inc.",
              personSlug: "lena-park",
              reason: "Test wall",
            },
          ],
        }),
      },
    };
    show("a", walled, "lena-park");
    expect(await screen.findByText("Showing 25 of 25")).toBeTruthy();
    expect(names().some((n) => n.startsWith("Granite Peak"))).toBe(false);
    expect(tiles().reduce((a, b) => a + b, 0)).toBe(25);
    const seg = segments();
    expect(
      (seg["Financial statement"] ?? 0) + (seg.EBP ?? 0) + (seg["Review & compilation"] ?? 0),
    ).toBe(25);
    expect(screen.getByText(/^25 engagements · /u)).toBeTruthy();
  });
});

describe("AUD-01 route /audits", () => {
  function route(scenario: Scenario, at = "/audits"): void {
    install(scenario);
    const Page = auditsRoute.options.component as () => JSX.Element;
    renderRoutes([{ path: "/audits", component: Page }], { at });
  }

  function flagOff(): Scenario {
    const base = scenarios.a.handlers["GET /v1/me/capabilities"];
    return {
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        "GET /v1/me/capabilities": async (request) => {
          const body = (await (base?.(request) ?? json({}))).json() as Promise<
            Record<string, unknown>
          >;
          return json({ ...(await body), flags: {} });
        },
      },
    };
  }

  it("flag off (audits.cockpit): the flag-off state, never a 404", async () => {
    route(flagOff());
    expect(await screen.findByText("Audits is not turned on for this firm.")).toBeTruthy();
    expect(document.querySelector("[data-flag-off='audits.cockpit']")).not.toBeNull();
  });

  it("the filters live in the URL: a shared link reopens the same list", async () => {
    route(scenarios.a, "/audits?phase=ready_to_release");
    expect(await screen.findByText("Showing 2 of 27")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Phase.*Ready to release/ })).toBeTruthy();
  });
});

describe("AUD-01 avoid", () => {
  it("AUD-01 avoid: zebra rows, 600/700 weights, the words Accrual/Arc/ACME/LSA, and task for a to-do", async () => {
    show("a");
    await screen.findByText("Showing 27 of 27");
    const html = document.body.innerHTML;
    expect(/odd:|even:/u.test(html)).toBe(false);
    expect(/font-(semibold|bold)/u.test(html)).toBe(false);
    expect(/\b(Accrual|Arc|ACME|LSA)\b/u.test(document.body.textContent)).toBe(false);
    expect(/\btasks?\b/iu.test(document.body.textContent)).toBe(false);
  });
});
