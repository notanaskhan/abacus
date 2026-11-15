// A-09-T08 (SPEC-658 AC-0.7): EntityTree reorders, indents and outdents by keyboard alone and
// announces each move; MilestoneTimeline says Late in text; CoverageBar has an equal table path.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CoverageBar } from "./CoverageBar";
import { type EntityNode, EntityTree, moveEntity, shiftEntity } from "./EntityTree";
import { MilestoneTimeline } from "./MilestoneTimeline";

afterEach(cleanup);

const NODES: EntityNode[] = [
  { id: "h", name: "Holdings", level: 1 },
  { id: "o", name: "Operating", level: 2 },
  { id: "m", name: "Manufacturing", level: 3 },
  { id: "d", name: "Distribution", level: 3 },
  { id: "r", name: "Real Estate", level: 2 },
];
const order = (ns: EntityNode[] | null): string =>
  (ns ?? []).map((n) => `${n.id}${String(n.level)}`).join(" ");

describe("EntityTree", () => {
  it("moves a subtree past its sibling's", () => {
    expect(order(moveEntity(NODES, 4, -1))).toBe("h1 r2 o2 m3 d3");
    expect(order(moveEntity(NODES, 1, 1))).toBe("h1 r2 o2 m3 d3");
    expect(moveEntity(NODES, 0, -1)).toBeNull();
  });

  it("indents under the sibling above, never past three tiers, and keeps one root", () => {
    expect(order(shiftEntity(NODES, 4, 1))).toBe("h1 o2 m3 d3 r3");
    expect(shiftEntity(NODES, 3, 1)).toBeNull(); // a fourth tier
    expect(order(shiftEntity(NODES, 3, -1))).toBe("h1 o2 m3 d2 r2");
    expect(shiftEntity(NODES, 1, -1)).toBeNull(); // a second root
  });

  it("reorders by keyboard alone and announces it", () => {
    let current = NODES;
    const { rerender } = render(
      <EntityTree label="Structure" nodes={current} onChange={(n) => (current = n)} />,
    );
    const rows = screen.getAllByRole("row");
    expect(rows.map((r) => r.getAttribute("aria-level"))).toEqual(["1", "2", "3", "3", "2"]);
    fireEvent.keyDown(rows[4] as HTMLElement, { key: "ArrowUp", altKey: true });
    rerender(<EntityTree label="Structure" nodes={current} onChange={(n) => (current = n)} />);
    expect(order(current)).toBe("h1 r2 o2 m3 d3");
    expect(document.querySelector("[data-entity-tree-status]")?.textContent).toBe(
      "Real Estate: level 2, position 2 of 5",
    );
  });

  it("a read-only tree refuses moves", () => {
    render(<EntityTree label="Structure" nodes={NODES} />);
    expect(screen.getByRole("treegrid").getAttribute("aria-readonly")).toBe("true");
  });
});

describe("MilestoneTimeline", () => {
  it("says Late in text", () => {
    render(
      <MilestoneTimeline
        label="Milestones"
        milestones={[
          { key: "i", label: "Interim memo", due: "Nov 30", state: "late", note: "Late · 1 day" },
        ]}
      />,
    );
    expect(screen.getByText("Late · 1 day")).toBeTruthy();
  });
});

describe("CoverageBar", () => {
  it("switches to an equal table", () => {
    render(
      <CoverageBar
        label="Coverage"
        measures={[
          {
            key: "ta",
            label: "Total assets",
            total: "50,760,000",
            segments: [
              { key: "full_scope", label: "Full scope", pct: 78, amount: "39,760,000" },
              {
                key: "specific_procedures",
                label: "Specific procedures",
                pct: 22,
                amount: "11,000,000",
              },
            ],
          },
        ]}
      />,
    );
    expect(screen.getByText("Full scope 78%")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "View as table" }));
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByText("39,760,000")).toBeTruthy();
  });
});
