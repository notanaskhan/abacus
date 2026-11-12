// P-02-T11 (TASK-7619): the SHL-02 fixtures foot to the handoff and to C15's rules. Groups come
// in canonical order, e is exactly a without the walled rows (no count, no note), every row opens
// a screen the manifest knows, and every response validates against the OpenAPI document.
import { describe, expect, it } from "vitest";
import { MANIFEST } from "../routes/manifest";
import { validateResponse } from "./schema-check";
import {
  SHL02_A,
  SHL02_B_RECENTS,
  SHL02_C,
  SHL02_D,
  SHL02_E,
  SHL02_F,
  SHL02_G,
} from "./seed/shl02";

const ORDER = [
  "clients",
  "returns",
  "audits",
  "closes",
  "binders",
  "files",
  "inbox",
  "sessions",
  "todos",
  "saved_prompts",
  "agents",
];

describe("SHL-02 fixtures", () => {
  it.each([
    ["a", SHL02_A],
    ["c", SHL02_C],
    ["d", SHL02_D],
    ["e", SHL02_E],
    ["f", SHL02_F],
    ["g", SHL02_G],
  ])("%s validates and keeps the canonical group order", (_, results) => {
    expect(validateResponse("post", "/v1/search", results)).toEqual([]);
    const groups = results.groups.map((g) => g.group);
    expect(groups).toEqual([...groups].sort((x, y) => ORDER.indexOf(x) - ORDER.indexOf(y)));
    expect(results.total_visible).toBeLessThanOrEqual(99);
  });

  it("e is a without the walled rows, and nothing counts them (DEC-43)", () => {
    const keep = new Set(SHL02_E.groups.flatMap((g) => g.items.map((i) => i.object_id)));
    const fromA = SHL02_A.groups.flatMap((g) => g.items).filter((i) => keep.has(i.object_id));
    expect(SHL02_E.groups.flatMap((g) => g.items)).toEqual(fromA);
    expect(JSON.stringify(SHL02_E)).not.toMatch(/hidden|wall/i);
    expect(SHL02_E.total_visible).toBe(fromA.length);
  });

  it("the 1065 is found by its partner and says who (story 1.1)", () => {
    const returns = SHL02_A.groups.find((g) => g.group === "returns");
    expect(returns?.items.map((i) => i.context)).toContain("Jonah Feld, limited partner 25%");
  });

  it("recents validate, five of them", () => {
    expect(validateResponse("get", "/v1/search/recents", SHL02_B_RECENTS)).toEqual([]);
    expect(SHL02_B_RECENTS.items).toHaveLength(5);
  });

  it("every row opens a screen the manifest knows", () => {
    const screens = new Set(Object.keys(MANIFEST));
    for (const r of [SHL02_A, SHL02_C, SHL02_E, SHL02_F, SHL02_G]) {
      for (const g of r.groups)
        for (const i of g.items) expect(screens).toContain(i.target.screen_id);
    }
    expect(screens).toContain(SHL02_D.suggestion?.target.screen_id);
  });
});
