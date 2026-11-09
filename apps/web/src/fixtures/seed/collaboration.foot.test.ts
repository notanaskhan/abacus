// P-05-T03: the collaboration fixture slice foots (SPEC-650 AC-29: 4 = 1 + 1 + 2) and keeps the
// handoff's boundaries: never the agent, Simone greyed, the shared thread never converts.
import { describe, expect, it } from "vitest";
import {
  componentThread,
  dividendsThread,
  mentionCandidates,
  myTodos,
  NORTHWIND_TEAM,
  row3Thread,
  row6Todo,
} from "./collaboration";

describe("collaboration fixtures", () => {
  it("SHL-17f: Marcus's open to-dos foot 1 + 1 + 2 = 4", () => {
    const page = myTodos();
    const c = page.counts ?? {};
    expect((c.overdue ?? 0) + (c.today ?? 0) + (c.this_week ?? 0)).toBe(4);
    expect(page.items).toHaveLength(4);
    expect(page.items.filter((t) => t.overdue)).toHaveLength(1);
  });

  it("SHL-17a: the row 6 to-do has 4 checklist items, at most 8", () => {
    const todo = row6Todo();
    expect(todo.checklist).toHaveLength(4);
    expect(todo.assignee.name).toBe("Marcus Delaney");
    expect(todo.due_on).toBe("2026-09-16");
  });

  it("SHL-18b2: five people on Northwind PY2025, Margaret marked as the viewer", () => {
    expect(NORTHWIND_TEAM).toHaveLength(5);
    expect(NORTHWIND_TEAM.filter((p) => p.is_self).map((p) => p.name)).toEqual([
      "Margaret Okonkwo",
    ]);
    expect(mentionCandidates("b2").team?.member_count).toBe(5);
    expect(NORTHWIND_TEAM.some((p) => /agent/i.test(p.name))).toBe(false);
  });

  it("SHL-18c: Simone Baptiste is listed greyed and not selectable", () => {
    const c = mentionCandidates("c");
    expect(c.members).toHaveLength(0);
    expect(c.not_on_engagement?.[0]).toMatchObject({
      name: "Simone Baptiste",
      selectable: false,
      reason: "not_on_engagement",
    });
  });

  it("SHL-18a/d/f: thread states and the shared-thread guard", () => {
    expect(row3Thread().allowed_actions).toContain("review_note.raise");
    expect(dividendsThread().status).toBe("resolved");
    expect(componentThread().visibility).toBe("shared");
    expect(componentThread().allowed_actions).not.toContain("review_note.raise");
  });
});
