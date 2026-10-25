// ENG-01's figures on the seed (P-07-T27; docs/screens/ENG-01.md, Figures): under "Period │
// Current" (DEC-343) the segments foot to 224 + 25 + 23 + 1 = 273 and the tiles to 1 + 4 + 0 + 128
// + 0 + 140 + 0 = 273; over every period to 275 with Archived 2; the summary's
// prospect and awaiting-letter counts are the Prospect and Accepted tiles, "2 past due" is
// Copperleaf and Bluebird, and every scenario's tiles and segments sum to its total.
import type { EngagementIndexPage } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../app-core/fixture-mode";
import { engagementIndexPage } from "./handlers/engagements";
import { getSeed } from "./seed";
import {
  ENG01_COUNTS,
  ENG01_CURRENT_COUNTS,
  ENG01_CURRENT_SEGMENTS,
  ENG01_ROWS,
  ENG01_SEGMENTS,
  ENG01_TILES,
} from "./seed/engagement-index";

const seed = getSeed();

function page(
  query: Record<string, string> = {},
  persona = "margaret-okonkwo",
): EngagementIndexPage {
  const request: FixtureRequest = {
    method: "GET",
    path: "/v1/engagements/index",
    params: {},
    query: new URLSearchParams(query),
    body: null,
    persona,
  };
  return engagementIndexPage(seed, request);
}

const tileSum = (p: EngagementIndexPage): number =>
  ENG01_TILES.reduce((sum, t) => sum + (p.counts?.[t] ?? 0), 0);
const segmentSum = (p: EngagementIndexPage): number =>
  (p.facets?.service_line ?? []).reduce((sum, f) => sum + f.n, 0);

describe("ENG-01 footing on the seed", () => {
  it("a (Current, DEC-343): segments 224 + 25 + 23 + 1 and tiles 1 + 4 + 0 + 128 + 0 + 140 + 0 = 273", () => {
    const a = page();
    expect(a.total).toBe(273);
    expect(Object.fromEntries((a.facets?.service_line ?? []).map((f) => [f.value, f.n]))).toEqual(
      ENG01_CURRENT_SEGMENTS,
    );
    expect(a.counts).toEqual(ENG01_CURRENT_COUNTS);
    expect(tileSum(a)).toBe(273);
    // Juniper & Oak's archived preparation (row 17) is a Prior row, not a Current one.
    expect(a.items).toHaveLength(ENG01_ROWS.length - 1);
    expect(a.items.some((r) => r.status === "archived")).toBe(false);
    expect(a.summary).toEqual({ prospect: 1, awaiting_letter: 4, past_due: 2 });
    expect(
      a.items.filter((r) => r.next_due?.tone === "past_due").map((r) => r.client_name),
    ).toEqual(["Copperleaf Coffee Roasters, Inc.", "Bluebird Bakery Co."]);
  });

  it("Period │ All counts the two archived audits under Archived: 275; Prior is those two", () => {
    const all = page({ period: "all" });
    expect(all.total).toBe(275);
    expect(all.counts).toEqual(ENG01_COUNTS);
    expect(
      Object.fromEntries((all.facets?.service_line ?? []).map((f) => [f.value, f.n])),
    ).toEqual(ENG01_SEGMENTS);
    expect(tileSum(all)).toBe(275);
    expect(all.items).toHaveLength(ENG01_ROWS.length);
    const prior = page({ period: "prior" });
    expect(prior.total).toBe(2);
    expect(tileSum(prior)).toBe(2);
    expect(prior.items.map((r) => r.client_name)).toEqual(["Juniper & Oak Interiors, LLC"]);
  });

  it("b: Letter │ Not signed with Accepted is the four letters out, never the Prospect", () => {
    const b = page({ letter: "not_signed", tile: "accepted" });
    expect(b.total).toBe(4);
    expect(b.items.map((r) => r.status)).toEqual(["accepted", "accepted", "accepted", "accepted"]);
    expect(tileSum(b)).toBe(4);
  });

  it("c: the Advisory segment is one Accepted engagement", () => {
    const c = page({ service_line: "advisory" });
    expect(c.total).toBe(1);
    expect(c.counts).toEqual({
      ...Object.fromEntries(ENG01_TILES.map((t) => [t, 0])),
      accepted: 1,
    });
  });

  it("d: Harbor Lane matches nothing", () => {
    expect(page({ q: "Harbor Lane" }).total).toBe(0);
  });

  it("every line's tiles foot to its segment, and segments ignore the line and the tile", () => {
    for (const line of ["tax", "audit", "cas", "advisory"] as const) {
      const p = page({ service_line: line, tile: "active" });
      expect(tileSum(p)).toBe(ENG01_CURRENT_SEGMENTS[line]);
      expect(segmentSum(p)).toBe(273);
      const every = page({ service_line: line, tile: "active", period: "all" });
      expect(tileSum(every)).toBe(ENG01_SEGMENTS[line]);
      expect(segmentSum(every)).toBe(275);
    }
  });
});
