import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HUMAN_VERBS } from "../attribution/actor";
import { GatesSpecimen } from "../specimens/gates";
import { ApprovalCard, type DiffRow, uncited } from "./approval-card";
import { DecisionCard } from "./decision-card";
import { SignOffSlots } from "./sign-off-slots";

// P-04-T40 acceptance: "The specimens render in /components with axe clean (e2e/components.spec.ts
// covers every specimen), and no gate verb renders through anything but HumanAction."

afterEach(cleanup);

const HANNAH = { kind: "human", name: "Hannah Leclerc" } as const;
const AGENT = { kind: "agent" } as const;

const ROWS: DiffRow[] = [
  { key: "a", label: "Contributions receivable", before: null, after: "48600.00", cites: 1 },
];

/** Every control whose name starts with a gate verb must be a HumanAction. */
function verbControls(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>("button, a, [role=button]")).filter((el) =>
    HUMAN_VERBS.some((v) => el.textContent.trim().startsWith(v)),
  );
}

describe("E7 gate kit", () => {
  it("test_ac2: every gate verb in the specimens renders through HumanAction", () => {
    const { container } = render(<GatesSpecimen />);
    const controls = verbControls(container);
    expect(controls.length).toBeGreaterThan(0);
    for (const el of controls) expect(el.getAttribute("data-human-verb")).not.toBeNull();
  });

  it("renders no gate verb for the agent", () => {
    const { container } = render(
      <>
        <ApprovalCard title="AJE" actor={AGENT} rows={ROWS} />
        <SignOffSlots
          slots={[{ level: "L2", role: "Reviewer", signer: null, at: null }]}
          next="L2"
          actor={AGENT}
        />
        <DecisionCard
          title="Receivable"
          reservedNote="Reserved."
          options={[{ key: "x", label: "X" }]}
          value="x"
          actor={AGENT}
        />
      </>,
    );
    expect(verbControls(container)).toHaveLength(0);
  });

  it("blocks Approve while a change has no citation", () => {
    const bare = ROWS.map((r) => ({ ...r, cites: 0 }));
    expect(uncited(bare)).toBe(1);
    render(<ApprovalCard title="AJE" actor={HANNAH} rows={bare} />);
    expect(screen.getByRole<HTMLButtonElement>("button", { name: /^Approve/u }).disabled).toBe(
      true,
    );
    expect(screen.getByText("1 change has no citation")).toBeTruthy();
  });

  it("approves a cited change", () => {
    const onApprove = vi.fn();
    render(<ApprovalCard title="AJE" actor={HANNAH} rows={ROWS} onApprove={onApprove} />);
    fireEvent.click(screen.getByRole("button", { name: /^Approve/u }));
    expect(onApprove).toHaveBeenCalledOnce();
  });

  it("holds Sign off while a check fails", () => {
    render(
      <SignOffSlots
        slots={[{ level: "L2", role: "Reviewer", signer: null, at: null }]}
        next="L2"
        actor={HANNAH}
        checks={[{ key: "n", label: "Review notes cleared", ok: false }]}
      />,
    );
    expect(screen.getByRole<HTMLButtonElement>("button", { name: /^Sign off/u }).disabled).toBe(
      true,
    );
  });

  it("holds Decide until an option is chosen; the recommendation is a tag, not a choice", () => {
    render(
      <DecisionCard
        title="Receivable"
        reservedNote="Reserved."
        options={[
          { key: "book", label: "Book it", recommended: true },
          { key: "no", label: "Disclose only" },
        ]}
        actor={HANNAH}
      />,
    );
    expect(screen.getByRole<HTMLButtonElement>("button", { name: /^Decide/u }).disabled).toBe(
      true,
    );
    for (const r of screen.getAllByRole("radio"))
      expect(r.getAttribute("aria-checked")).not.toBe("true");
  });
});
