// KNW-01 figures that must foot (KNW-01 handoff acceptance checklist; K-01-T04), on the knowledge
// slice of the seed and through the scenario handlers.
import type { ListPageKnowledgeItemOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { scenarios } from "./scenarios/KNW-01";
import { knowledgeItems, reviewQueue } from "./seed/knowledge";

async function page(persona: string, query = ""): Promise<ListPageKnowledgeItemOut> {
  const handler = scenarios.a.handlers["GET /v1/knowledge/items"];
  const response = await handler?.({
    method: "GET",
    path: "/v1/knowledge/items",
    params: {},
    query: new URLSearchParams(query),
    body: null,
    persona,
  });
  if (response === undefined) throw new Error("no handler");
  return (await response.json()) as ListPageKnowledgeItemOut;
}

describe("KNW-01 footings", () => {
  it("categories: 4 + 12 + 12 + 6 + 14 = 48; statuses: 46 + 1 + 1 = 48", async () => {
    const all = await page("margaret-okonkwo");
    const facets = Object.fromEntries((all.facets?.category ?? []).map((f) => [f.value, f.n]));
    expect(facets).toEqual({
      methodology: 4,
      firm_standards: 12,
      pbc_templates: 12,
      research: 6,
      agent_instructions: 14,
    });
    expect(Object.values(facets).reduce((a, b) => a + b, 0)).toBe(48);
    expect(all.counts).toEqual({ published: 46, draft: 1, superseded: 1 });
    expect(knowledgeItems()).toHaveLength(48);
  });

  it("usage ties to §9.5: EBP 14 · FS 6 · SSARS 7 = 27; checklists 162 + 38 + 12 + 5 + 6 + 1 = 224", () => {
    const usage = (title: string, version: string) =>
      knowledgeItems().find((i) => i.title === title && i.version_label === version)?.usage_count;
    const methodology = [
      usage("BH Audit Methodology · EBP", "v3"),
      usage("BH Audit Methodology · FS", "v5"),
      usage("BH SSARS Methodology · Review, Compilation & Preparation", "v2"),
    ];
    expect(methodology.reduce((a, b) => (a ?? 0) + (b ?? 0), 0)).toBe(27);
    const checklists = knowledgeItems()
      .filter((i) => i.usage_kind === "returns" && i.title.includes("Review Checklist"))
      .map((i) => i.usage_count ?? 0);
    expect(checklists.reduce((a, b) => a + b, 0)).toBe(224);
    expect(knowledgeItems().filter((i) => i.category === "agent_instructions")).toHaveLength(14);
  });

  it("the review queue's 2 are the §754 memo and the 1040 checklist v7, a draft inside card 6", () => {
    expect(reviewQueue().map((r) => r.title)).toEqual([
      "1040 Review Checklist",
      "§754 election — Ridgeline",
    ]);
  });

  it("a reader who neither manages nor approves gets no draft and 47 cards", async () => {
    const ana = await page("ana-cruz");
    expect(ana.counts).toEqual({ published: 46, draft: 0, superseded: 1 });
    expect(ana.total).toBe(47);
  });

  it("an empty search category counts nothing and a search ranges the title", async () => {
    const found = await page("margaret-okonkwo", "q=materiality");
    expect(found.items.map((i) => [i.title, i.match])).toEqual([
      ["Materiality ranges", [{ start: 0, end: 11 }]],
      ["BH Audit Methodology · EBP", []],
    ]);
  });
});
