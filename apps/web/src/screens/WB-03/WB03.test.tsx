// W-02-T21 (TASK-7948; docs/screens/WB-03.md a, a2, b–g, d2): "WB-03 a, a2, b-g and d2 pass in
// Vitest with axe clean, and no Approve control renders for a viewer who is not the owner."
// The plan card here; gathering, results, the artifact row and the preview are the kit's rows on
// the session's items (their own suites); axe at the S43 end pass.
import type { RunPlanOut } from "@abacus/api-client";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { COPY } from "./copy";
import { PlanCardView } from "./PlanCard";

afterEach(cleanup);

const PLAN: RunPlanOut = {
  id: "p1",
  run_id: "r1",
  version: 1,
  state: "proposed",
  steps: [
    { key: "s1", label: "Read TY2025 returns, engagements and binders (read-only)", level: 0, writes: false },
    { key: "s2", label: "Group open returns by stage and office", level: 1, writes: false },
    { key: "s3", label: "Build the workbook: Summary, Gather, Prepare, Review, Deliver", level: 2, writes: false },
    { key: "s4", label: "Save the workbook to Files", level: 3, writes: true },
  ],
  sources: [],
  reads: [
    { source: "tax_returns", label: "Tax returns", count: 224 },
    { source: "tax_engagements", label: "Tax engagements", count: 214 },
    { source: "binders", label: "Binders", count: 241 },
    { source: "offices", label: "Offices", count: 3 },
  ],
  writes: [
    {
      step_key: "s4",
      action: "file.propose",
      label: "Create file TY2025 Season Progress — by office.xlsx in Files › Firm reports › TY2025 season",
      approver_name: "Hannah Leclerc",
    },
  ],
};

describe("WB-03 run arc: the plan card", () => {
  it("a: numbered steps, the data it will read and the write that needs approval", () => {
    render(<PlanCardView plan={PLAN} canDecide />);
    expect(screen.getByText(COPY.planReady)).toBeTruthy();
    expect(document.querySelector("[data-plan-reads]")?.textContent).toBe(
      "Tax returns 224 · Tax engagements 214 · Binders 241 · Offices 3",
    );
    expect(document.querySelector("[data-plan-writes]")?.textContent).toContain("Hannah Leclerc");
  });

  it("the owner approves; a viewer who is not the owner sees no Approve control", () => {
    const approve = vi.fn();
    render(<PlanCardView plan={PLAN} canDecide onApprove={approve} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.approvePlan }));
    expect(approve).toHaveBeenCalled();
    cleanup();
    render(<PlanCardView plan={PLAN} canDecide={false} />);
    expect(screen.queryByRole("button", { name: COPY.approvePlan })).toBeNull();
  });

  it("a2: Edit plan turns the steps into fields and saves the reworded labels", () => {
    const save = vi.fn();
    render(<PlanCardView plan={PLAN} canDecide onSaveEdit={save} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.editPlan }));
    fireEvent.change(screen.getByLabelText(COPY.stepLabel(2)), {
      target: { value: "Group open returns by office" },
    });
    fireEvent.click(screen.getByRole("button", { name: COPY.saveEdit }));
    expect(save).toHaveBeenCalledWith({ s2: "Group open returns by office" });
  });

  it("g: a cancelled plan reads one muted line", () => {
    render(
      <PlanCardView
        plan={{ ...PLAN, state: "cancelled", decided_by: "Hannah Leclerc", decided_at: "2026-09-14T14:24:00Z" }}
        canDecide
      />,
    );
    expect(document.querySelector("[data-plan='cancelled']")?.textContent).toBe(
      "Plan cancelled by Hannah Leclerc · 9:24 AM",
    );
  });
});
