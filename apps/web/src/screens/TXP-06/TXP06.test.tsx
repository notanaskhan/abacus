// T-05-T44 (TASK-7707; docs/screens/TXP-06.md; handoff TXP-06 A–D): "All six artboards render,
// editing a rung previews without persisting, and Esc returns to TXP-05." Figures are the server's
// (the fixture stands in for it).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CITATIONS, harborview, ridgeline } from "../../fixtures/seed/tax-entity-allocation";
import { COPY } from "./copy";
import { TXP06 } from ".";

afterEach(cleanup);

describe("TXP-06 Allocation Structure", () => {
  it("A: Ridgeline's two periods of 628,100 and the partner totals to 1,256,200", () => {
    render(<TXP06 structure={ridgeline()} forceOpen approvedBy="Samuel Ito" approvedOn="Sep 9" />);
    expect(screen.getAllByText("1,256,200").length).toBeGreaterThan(0);
    expect(screen.getByText("1/1–6/30/2025 · 628,100")).toBeTruthy();
    expect(screen.getByText("7/1–12/31/2025 · 628,100")).toBeTruthy();
    expect(screen.getAllByText("477,356").length).toBeGreaterThan(0);
    expect(screen.getByText(COPY.approved("Samuel Ito", "Sep 9"))).toBeTruthy();
    expect(screen.queryByText(COPY.approve)).toBeNull();
    expect(screen.queryByText(/\$/)).toBeNull();
  });

  it("A: Pell Street II receives nothing in period 1", () => {
    const { container } = render(<TXP06 structure={ridgeline()} forceOpen />);
    const ps2 =
      ridgeline().partners?.find((p) => p.name === "Pell Street II LLC")?.partner_id ?? "";
    expect(container.querySelector(`[data-segment="p1:${ps2}"]`)).toBeNull();
    expect(container.querySelector(`[data-segment="p2:${ps2}"]`)).not.toBeNull();
  });

  it("A2: picking Meera Shah outlines her series in every bar", () => {
    const shah = ridgeline().partners?.find((p) => p.name === "Meera Shah")?.partner_id ?? "";
    const { container } = render(<TXP06 structure={ridgeline()} forceOpen selected={shah} />);
    const outlined = container.querySelectorAll(".outline");
    expect(outlined.length).toBe(2);
  });

  it("B: Harborview's rungs foot to 4,900,000 and the back-solve plugs 900,000 at 20%", () => {
    render(<TXP06 structure={harborview()} forceOpen />);
    expect(screen.getByText("Return of Capital")).toBeTruthy();
    expect(screen.getByText("8% Preferred Return")).toBeTruthy();
    expect(screen.getByText("100% GP Catch-up to 20%")).toBeTruthy();
    expect(screen.getAllByText("4,900,000").length).toBeGreaterThan(0);
    expect(screen.getAllByText("900,000").length).toBeGreaterThan(0);
    expect(screen.getByText(COPY.gpShare("20"))).toBeTruthy();
    expect(screen.getAllByText("2,843,077").length).toBeGreaterThan(0);
  });

  it("C: Pending approval shows the reader's reasoning with two citations and Approve structure", () => {
    const onApprove = vi.fn();
    const onCitation = vi.fn();
    render(
      <TXP06
        structure={ridgeline(true)}
        forceOpen
        onApprove={onApprove}
        onCitation={onCitation}
      />,
    );
    expect(screen.getByText(COPY.ridgeline.reasoning)).toBeTruthy();
    expect(screen.getByText(COPY.citations(2))).toBeTruthy();
    fireEvent.click(screen.getByText("[1]"));
    expect(onCitation).toHaveBeenCalledWith(CITATIONS[0]);
    fireEvent.click(screen.getByText(COPY.approve));
    expect(onApprove).toHaveBeenCalledOnce();
    expect(screen.getAllByText(COPY.pending).length).toBe(3);
  });

  it("D: editing a rung previews and the back-solve reads Pending until Save", () => {
    const onRung = vi.fn();
    const onSave = vi.fn();
    render(
      <TXP06
        structure={harborview()}
        preview={harborview({ pref: "9", catchUp: "20", gp: "20" })}
        forceOpen
        editing={2}
        onRung={onRung}
        onSave={onSave}
      />,
    );
    fireEvent.change(screen.getByRole("textbox", { name: "9% Preferred Return" }), {
      target: { value: "9.5" },
    });
    expect(onRung).toHaveBeenCalledWith(2, "9.5");
    expect(screen.getAllByText(COPY.pending).length).toBeGreaterThanOrEqual(2);
    fireEvent.click(screen.getByText(COPY.save));
    expect(onSave).toHaveBeenCalledOnce();
  });

  it("Esc in a rung field leaves edit mode before the sheet closes", () => {
    const onEdit = vi.fn();
    render(<TXP06 structure={harborview()} forceOpen editing={2} onEdit={onEdit} />);
    fireEvent.keyDown(screen.getByRole("textbox", { name: "8% Preferred Return" }), {
      key: "Escape",
    });
    expect(onEdit).toHaveBeenCalledWith(null);
  });
});
