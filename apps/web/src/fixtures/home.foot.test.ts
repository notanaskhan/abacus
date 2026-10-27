// HOME-01 figures that must foot (docs/screens/HOME-01.md, Figures; I-01-T05), on the home slice
// of the E0 seed and through the scenario handlers the screen reads.
import type { HomeOut, HumanGateCountsOut, HumanGateOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { countsOf, gatesFor } from "./handlers/human-gates";
import { scenarios } from "./scenarios/HOME-01";
import { getSeed } from "./seed";
import { homeGates, homeView } from "./seed/home";

const seed = getSeed();

async function call<T>(
  state: keyof typeof scenarios,
  route: string,
  persona: string,
  query = "",
): Promise<T> {
  const handler = scenarios[state].handlers[route];
  const response = await handler?.({
    method: "GET",
    path: route.split(" ")[1] ?? "",
    params: {},
    query: new URLSearchParams(query),
    body: null,
    persona,
  });
  if (response === undefined) throw new Error(`no handler for ${route}`);
  return (await response.json()) as T;
}

const n = (tile: HomeOut["tiles"][number], code: string): number =>
  tile.by_status.find((s) => s.code === code)?.n ?? 0;

describe("HOME-01 tiles foot (blueprint §9.5)", () => {
  const tiles = Object.fromEntries(homeView("daniel-reyes").tiles.map((t) => [t.key, t]));

  it("tax: 17 + 15 + 11 + 7 = 50 of the 79 open, and the 79 foot by status", () => {
    const returns = tiles.returns;
    if (returns === undefined) throw new Error("no returns tile");
    const shown = ["prepared", "in_review", "action_required", "approved"].map((c) =>
      n(returns, c),
    );
    expect(shown).toEqual([17, 15, 11, 7]);
    expect(shown.reduce((a, b) => a + b, 0)).toBe(50);
    expect(returns.total).toBe(79);
    expect(returns.by_status.reduce((a, s) => a + s.n, 0)).toBe(79);
    // TY2025 returns 224 = 98 + 64 + 62 by office (TPL-11f).
    expect(returns.by_office.reduce((a, o) => a + o.n, 0)).toBe(224);
  });

  it("audits 7 + 9 + 6 + 2 + 3 = 27; closes 11 of 22; notices 9 with 2 New", () => {
    const audits = tiles.audits;
    const closes = tiles.closes;
    const notices = tiles.notices;
    if (audits === undefined || closes === undefined || notices === undefined) throw new Error();
    expect(audits.by_status.map((s) => s.n)).toEqual([7, 9, 6, 2, 3]);
    expect(audits.by_status.reduce((a, s) => a + s.n, 0)).toBe(audits.total);
    expect(audits.total).toBe(27);
    expect([n(closes, "in_progress"), closes.total]).toEqual([11, 22]);
    expect(closes.by_status.reduce((a, s) => a + s.n, 0)).toBe(22);
    expect([notices.total, n(notices, "received")]).toEqual([9, 2]);
  });
});

describe("HOME-01 Waiting on you foots (one count source)", () => {
  it("Daniel 11 = 3 + 6 + 2; the counts call and the list agree", async () => {
    const counts = await call<HumanGateCountsOut>(
      "a",
      "GET /v1/human-gates/counts",
      "daniel-reyes",
    );
    expect(counts.total).toBe(11);
    expect(counts.bands).toEqual({
      decisions: 3,
      sign_offs: 6,
      agent_outputs: 0,
      approvals_sends: 2,
    });
    const list = await call<{ items: HumanGateOut[]; total: number }>(
      "a",
      "GET /v1/human-gates",
      "daniel-reyes",
    );
    expect(list.total).toBe(counts.total);
    // Every sign-off row is a Ridgeline section due Sep 15.
    const signOffs = list.items.filter((g) => g.band === "sign_offs");
    expect(
      signOffs.every((g) => g.title?.includes("Ridgeline") === true && g.due_on === "2026-09-15"),
    ).toBe(true);
  });

  it("Margaret 4 = 2 + 2; Samuel 6 = 0 + 4 + 2; Kevin 0; Grace 2", () => {
    const bands = (who: string) => countsOf(gatesFor(seed, who)).bands;
    expect(bands("margaret-okonkwo")).toEqual({
      decisions: 2,
      sign_offs: 0,
      agent_outputs: 0,
      approvals_sends: 2,
    });
    expect(bands("samuel-ito")).toEqual({
      decisions: 0,
      sign_offs: 4,
      agent_outputs: 2,
      approvals_sends: 0,
    });
    expect(countsOf(gatesFor(seed, "kevin-osei")).total).toBe(0);
    expect(countsOf(gatesFor(seed, "grace-holloway")).bands.approvals_sends).toBe(2);
  });

  it("f reads 0 everywhere; office narrows and never errors", async () => {
    const counts = await call<HumanGateCountsOut>(
      "f",
      "GET /v1/human-gates/counts",
      "daniel-reyes",
    );
    expect(counts.total).toBe(0);
    const nowhere = await call<HumanGateCountsOut>(
      "a",
      "GET /v1/human-gates/counts",
      "daniel-reyes",
      "office_id=00000000-0000-4000-8000-000000000000",
    );
    expect(nowhere.total).toBe(0);
  });

  it("your work: a2 Your returns 6, b Your engagements 4, d My work 4", () => {
    expect(homeView("daniel-reyes").your_work?.rows).toHaveLength(6);
    expect(homeView("margaret-okonkwo").your_work?.rows).toHaveLength(4);
    expect(homeView("kevin-osei").your_work?.rows).toHaveLength(4);
  });
});

describe("HOME-01 row figures foot", () => {
  const context = (needle: string): string =>
    homeGates("daniel-reyes").find((g) => g.title?.includes(needle) === true)?.context ?? "";

  it("Whitley: 1,870 + 1,250 = 3,120 and 22% × 3,120 = 686.40", () => {
    expect(context("CP2000")).toContain("1,870 + 1,250 = 3,120");
    expect(1870 + 1250).toBe(3120);
    expect((3120 * 22) / 100).toBe(686.4);
    expect(context("CP2000")).toContain("686.40");
  });

  it("Schedule K box 2 1,231,600 apportions and PTET foots to the dollar", () => {
    expect(context("Schedule K")).toContain("Box 2 1,231,600");
    const box2 = 1_231_600;
    const il = Math.round(box2 * 0.46);
    const co = Math.round(box2 * 0.315);
    const ny = Math.round(box2 * 0.225);
    expect([il, co, ny]).toEqual([566_536, 387_954, 277_110]);
    expect(il + co + ny).toBe(box2);
    expect([Math.round(il * 0.0495), Math.round(co * 0.044), Math.round(ny * 0.0685)]).toEqual([
      28_044, 17_070, 18_982,
    ]);
    expect(context("States & PTET")).toContain("PTET 28,044 / 17,070 / 18,982");
  });
});

describe("HOME-01 walled (INV-3, DEC-43)", () => {
  it("a walled client's gate is left out of the list and every count", () => {
    const wall = seed.walls.find((w) => w.personSlug === "lena-park");
    if (wall === undefined) throw new Error("the seed walls Lena from Ashford");
    const ashford = { ...homeGates("daniel-reyes")[0], client_id: wall.clientId } as HumanGateOut;
    const rows = (persona: string) => (persona === "lena-park" ? [ashford] : []);
    expect(gatesFor(seed, "lena-park", rows)).toEqual([]);
    expect(countsOf(gatesFor(seed, "lena-park", rows)).total).toBe(0);
  });

  it("Lena's E0 home holds no Ashford item", async () => {
    const home = await call<HomeOut>("walled", "GET /v1/home", "lena-park");
    expect(JSON.stringify(home)).not.toMatch(/Ashford/u);
  });
});
