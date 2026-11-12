// F-07-T04 (TPL-04 a–e). Acceptance: "Fixture tests prove 79 + 145 = 224, 98 + 64 + 62 = 224,
// 10 + 26 + 26 + 17 = 79 and 120 of 241 = 50%, and lint L10 finds no kit sample person."
import { describe, expect, it } from "vitest";
import {
  ARTIFACT,
  DISCOVERY,
  QUESTION,
  REQUEST,
  TPL04_FRAMES,
  groupTotals,
  sessionRows,
  threadItems,
  tpl04Script,
} from "./tpl04-sessions";

const SEED_PERSONAS = new Set([
  "Hannah Leclerc",
  "Marcus Delaney",
  "Grace Holloway",
  "Raj Malhotra",
  "Kevin Osei",
  "Daniel Reyes",
]);

describe("TPL-04 fixtures", () => {
  it("79 + 145 = 224 from the export", () => {
    expect(DISCOVERY.open + DISCOVERY.done).toBe(224);
    expect([DISCOVERY.open, DISCOVERY.done, DISCOVERY.returns]).toEqual([79, 145, 224]);
  });

  it("98 + 64 + 62 = 224 by office", () => {
    expect(DISCOVERY.offices).toEqual([98, 64, 62]);
    expect(DISCOVERY.offices.reduce((a, b) => a + b, 0)).toBe(224);
  });

  it("10 + 26 + 26 + 17 = 79 by stage", () => {
    const g = groupTotals();
    expect([g.Gather, g.Prepare, g.Review, g.Deliver]).toEqual([10, 26, 26, 17]);
    expect(g.Gather + g.Prepare + g.Review + g.Deliver).toBe(DISCOVERY.open);
  });

  it("120 of 241 = 50%", () => {
    expect(Math.round((DISCOVERY.bindersRead / DISCOVERY.binders) * 100)).toBe(50);
    const c = JSON.stringify(threadItems("c"));
    expect(c).toContain("120 of 241 · 50%");
  });

  it("eight session rows, owned by seed personas only (lint L10)", () => {
    const rows = sessionRows("a");
    expect(rows).toHaveLength(8);
    for (const r of rows) {
      const who = r.owner.kind === "human" ? r.owner.name : r.owner.person;
      expect(SEED_PERSONAS.has(who), who).toBe(true);
    }
    expect(rows.filter((r) => r.owner.kind === "agent_assisted").map((r) => r.title)).toEqual([
      "Season Progress Reporter — weekly run",
      "Request Chaser — daily",
    ]);
    expect(rows[0]?.needs_answer).toBe(true);
    expect(sessionRows("c")[0]?.running).toBe(true);
  });

  it.each(TPL04_FRAMES)("%s builds its thread from C6 kinds only", (frame) => {
    const kinds = new Set(threadItems(frame).map((i) => i.kind));
    const allowed = new Set([
      "user_message",
      "agent_blocks",
      "plan",
      "question",
      "answer",
      "tool_card",
      "artifact",
      "notice",
    ]);
    for (const k of kinds) expect(allowed.has(k), k).toBe(true);
  });

  it("a: the discovery table and the 1 of 2 question with Open returns only preselected", () => {
    const a = threadItems("a");
    expect(a[0]?.payload.body).toBe(REQUEST);
    expect(JSON.stringify(a)).toContain("What I found in Accrued:");
    expect(JSON.stringify(a)).not.toContain("Accrual");
    expect(QUESTION.steps[0]?.preselect).toBe("open");
    expect(a.at(-1)?.kind).toBe("question");
  });

  it("d: the result and the workbook; e: the CCH Axcess token failure", () => {
    const d = threadItems("d");
    expect(JSON.stringify(d)).toContain("Gather 10 · Prepare 26 · Review 26 · Deliver 17");
    expect(d.at(-1)?.payload).toMatchObject({ name: ARTIFACT.name, meta: "Excel · 5 tabs" });
    const e = JSON.stringify(threadItems("e"));
    expect(e).toContain("Stopped at Read binder status");
    expect(e).toContain("CCH Axcess token expired on Sep 12.");
    expect(threadItems("b")).toEqual([]);
  });

  it("the running script ticks the tool cards and ends succeeded", () => {
    const script = tpl04Script();
    expect(script.map((s) => s.page.run?.state)).toEqual(["running", "succeeded"]);
    expect(script.at(-1)?.page.items.every((i) => i.outcome === "succeeded" || i.seq === 2)).toBe(
      true,
    );
  });
});
