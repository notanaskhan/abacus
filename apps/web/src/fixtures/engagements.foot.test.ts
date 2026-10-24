// ENG-01's figures on the seed (P-07-T27; docs/screens/ENG-01.md, Figures): the segments foot to
// 224 + 27 + 23 + 1 = 275, the tiles to 1 + 4 + 0 + 128 + 0 + 140 + 2 = 275, the summary's
// prospect and awaiting-letter counts are the Prospect and Accepted tiles, "2 past due" is
// Copperleaf and Bluebird, and every scenario's tiles and segments sum to its total.
import type { EngagementIndexPage } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../app-core/fixture-mode";
import { engagementIndexPage } from "./handlers/engagements";
import { getSeed } from "./seed";
import { ENG01_COUNTS, ENG01_ROWS, ENG01_SEGMENTS, ENG01_TILES } from "./seed/engagement-index";

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
  it("a: segments 224 + 27 + 23 + 1 and tiles 1 + 4 + 0 + 128 + 0 + 140 + 2 = 275", () => {
    const a = page();
    expect(a.total).toBe(275);
    expect(Object.fromEntries((a.facets?.service_line ?? []).map((f) => [f.value, f.n]))).toEqual(
      ENG01_SEGMENTS,
    );
    expect(a.counts).toEqual(ENG01_COUNTS);
    expect(tileSum(a)).toBe(275);
    expect(a.items).toHaveLength(ENG01_ROWS.length);
    expect(a.summary).toEqual({ prospect: 1, awaiting_letter: 4, past_due: 2 });
    expect(
      a.items.filter((r) => r.next_due?.tone === "past_due").map((r) => r.client_name),
    ).toEqual(["Copperleaf Coffee Roasters, Inc.", "Bluebird Bakery Co."]);
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
      expect(tileSum(p)).toBe(ENG01_SEGMENTS[line]);
      expect(segmentSum(p)).toBe(275);
    }
  });
});
