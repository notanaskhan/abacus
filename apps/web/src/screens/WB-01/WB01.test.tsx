// W-02-T14 (TASK-7909; docs/screens/WB-01.md; SPEC-653 AC-L1–L5, AC-V2): the list pane and header.
// "WB-01c and f pass in Vitest with axe clean, and the list reads Running 3 at 9:24:00 and Running 4
// at 9:25." The counts and rows are the server's (the fixture stands in for it).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionList } from "@abacus/ui";
import { wbList } from "../../fixtures/seed/workbench";
import { COPY } from "./copy";
import { filterLabel, filterMenu, rowOf } from ".";

afterEach(cleanup);

function must<T>(v: T | null | undefined): T {
  if (v === null || v === undefined) throw new Error("expected an element");
  return v;
}

describe("WB-01 list pane", () => {
  it("c: the menu reads Running 3 at 9:24:00 and Running 4 at 9:25, Needs your answer 0", () => {
    const at924 = wbList("wb01c-running-three").counts;
    const at925 = wbList("wb01c-running-four").counts;
    expect(filterLabel("running", at924)).toBe("Running 3");
    expect(filterLabel("running", at925)).toBe("Running 4");
    expect(filterLabel("needs_answer", at924)).toBe("Needs your answer 0");
    const [items] = filterMenu("running", at924, undefined);
    expect(items?.map((i) => i.label)).toEqual([
      "All sessions",
      "Mine",
      "Via Agent",
      "Running 3",
      "Needs your answer 0",
    ]);
    expect(items?.find((i) => i.checked)?.label).toBe("Running 3");
  });

  it("c: the three close runs draw spinners and read via Agent", () => {
    const rows = wbList("wb01c-running-three").items.map((r) => rowOf(r));
    render(<SessionList rows={rows} still />);
    // The spinner's word is visually hidden inside its status (C-20).
    expect(screen.getAllByRole("status").filter((s) => s.textContent === "Running")).toHaveLength(
      3,
    );
    expect(screen.getByText(/Raj Malhotra via Agent/)).toBeTruthy();
  });

  it("f: a title search with no match says so with Clear search", () => {
    const onQuery = vi.fn();
    render(
      <SessionList rows={[]} query="K-3" emptyTitle={COPY.noMatch("K-3")} onQuery={onQuery} />,
    );
    expect(screen.getByText("No sessions match 'K-3'.")).toBeTruthy();
    fireEvent.click(screen.getByText(COPY.clearSearch));
    expect(onQuery).toHaveBeenCalledWith("");
  });

  it("a: row 1's amber dot and row 2's Ready for review", () => {
    const rows = wbList("wb01-list-e0").items.map((r) => rowOf(r));
    render(<SessionList rows={rows} still />);
    expect(screen.getAllByLabelText("Awaiting your answer")).toHaveLength(1);
    expect(screen.getByText("Ready for review")).toBeTruthy();
  });

  it("AC-L5: only the owner's own unlocked rows can be renamed or deleted", () => {
    const items = wbList("wb01-list-e0").items;
    const hannah = items[0]?.owner?.user_id ?? null;
    const manageable = items.map((r) => rowOf(r, hannah)).filter((r) => r.manageable);
    expect(manageable.every((r) => !r.locked)).toBe(true);
    expect(items.map((r) => rowOf(r, "someone-else")).some((r) => r.manageable)).toBe(false);
  });

  it("AC-L4: rename saves on Enter", () => {
    const items = wbList("wb01-list-e0").items;
    const hannah = items[0]?.owner?.user_id ?? null;
    const rows = items.map((r) => rowOf(r, hannah));
    const onRename = vi.fn();
    render(<SessionList rows={rows} still onRename={onRename} />);
    fireEvent.click(must(screen.getAllByLabelText("Rename session")[0]));
    const field = screen.getByLabelText("Session title");
    fireEvent.change(field, { target: { value: "Season progress by office" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onRename).toHaveBeenCalledWith(
      rows.find((r) => r.manageable)?.id,
      "Season progress by office",
    );
  });
});
