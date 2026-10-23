// BND-01 figures that must foot (docs/screens/BND-01.md, Figures; P-06 §5.4), on the binder slice.
import type { BinderStatus } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { scenarios } from "./scenarios/BND-01";
import { getSeed } from "./seed";
import {
  BINDER_COUNTS,
  BINDER_PARTS,
  BINDER_ROWS,
  OSTERBERG_ROW,
  toBinderRow,
} from "./seed/binders";
import { DEMO_MS } from "./seed/clock";

const seed = getSeed();

async function page(state: keyof typeof scenarios, query = "service=tax_returns&season=TY2025") {
  const handler = scenarios[state].handlers["GET /v1/binders"];
  const response = await handler?.({
    method: "GET",
    path: "/v1/binders",
    params: {},
    query: new URLSearchParams(query),
    body: null,
    persona: scenarios[state].persona,
  });
  return (await response?.json()) as {
    items: { client_name: string; status: BinderStatus }[];
    total: number;
    counts: Record<BinderStatus, number>;
  };
}

describe("binder slice footing", () => {
  it("tiles: 1 + 48 + 0 + 40 + 152 = 241, and 224 returns + 17 second-part binders = 241", () => {
    expect(Object.values(BINDER_COUNTS).reduce((a, b) => a + b, 0)).toBe(241);
    expect(BINDER_PARTS.returns + BINDER_PARTS.secondParts).toBe(241);
  });

  it("the 15 named rows sit inside their tiles", () => {
    expect(BINDER_ROWS).toHaveLength(15);
    for (const status of Object.keys(BINDER_COUNTS) as BinderStatus[]) {
      const named = BINDER_ROWS.filter((r) => r.status === status).length;
      expect(named, status).toBeLessThanOrEqual(BINDER_COUNTS[status]);
    }
  });

  it("Feld reads 5 of 7; Osterberg 0 of 9", () => {
    const feld = BINDER_ROWS.find((r) => r.client === "Jonah & Claire Feld");
    expect([feld?.done, feld?.total]).toEqual([5, 7]);
    expect([OSTERBERG_ROW.done, OSTERBERG_ROW.total]).toEqual([0, 9]);
  });

  it("every named client is a Brightwater Hale client of the seed", () => {
    for (const r of [...BINDER_ROWS, OSTERBERG_ROW]) {
      expect(
        seed.clients.some((c) => c.name === r.client),
        r.client,
      ).toBe(true);
      expect(toBinderRow(seed, r).preparer_user_id, r.prep).not.toBeNull();
    }
  });

  it("Fenwick, Aug 11, is 34 days before the demo clock: the only published binder silent 30 days", async () => {
    const fenwick = BINDER_ROWS.find((r) => r.client === "Fenwick Family Foundation");
    // Calendar days on the firm's calendar: Aug 11 → Sep 14.
    const day = (iso: string): number => Date.parse(iso.slice(0, 10)) / 86_400_000;
    expect(day("2026-09-14") - day(fenwick?.activity ?? "")).toBe(34);
    expect(DEMO_MS - Date.parse(fenwick?.activity ?? "")).toBeGreaterThan(30 * 86_400_000);
    const silent = await page(
      "a",
      "service=tax_returns&season=TY2025&client_activity=none_30_days",
    );
    expect(silent.items.map((r) => r.client_name)).toEqual(["Fenwick Family Foundation"]);
  });

  it("a: Showing 15 of 241; c: 16 of 241 with 47 Published and 1 Unpublished; d: TY2026 is empty", async () => {
    const a = await page("a");
    expect([a.items.length, a.total]).toEqual([15, 241]);
    const c = await page("c");
    expect([c.items.length, c.total, c.counts.published, c.counts.unpublished]).toEqual([
      16, 241, 47, 1,
    ]);
    const d = await page("d", "service=tax_returns&season=TY2026");
    expect([d.items.length, d.total]).toEqual([0, 0]);
  });
});
