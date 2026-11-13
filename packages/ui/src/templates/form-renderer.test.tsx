// F-07-T18 (TASK-7920; handoff T17, TPL-17 a, b): "T17a and T17b pass Tier D, the face holds no
// editable control, Go to pages to and lights the target field, and the total row shows the
// server's tie state without summing."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MatchScope } from "../tracing/match";
import { contractMatchId } from "../tracing/match-store";
import { FormRendererLayout } from "./form-renderer";

afterEach(cleanup);

const FILE = {
  name: "Ridgeline 2025 Form 1065",
  pages: [{ n: 1, width_pt: 612, height_pt: 792, rotation: 0 as const, src: "/f/1.png" }],
  regions: [],
};

function draw(props: Partial<Parameters<typeof FormRendererLayout>[0]> = {}) {
  return render(
    <MatchScope>
      <FormRendererLayout
        mode="form"
        thumbs={[{ n: 1, src: "/f/1.png", diagnostics: 2 }, { n: 2, src: null }]}
        page={1}
        file={FILE}
        k1s={[{ id: "feld", name: "Jonah Feld", amount: "307900", status: "Draft" }]}
        total={{ state: "off", difference: "-6200" }}
        diagnostics={[{ id: "d1", severity: "error", text: "M-2 line 9 ≠ Schedule L", page: 6, match: contractMatchId({ match_id: "p6.m2_9" }) }]}
        {...props}
      />
    </MatchScope>,
  );
}

describe("T17 FormRendererLayout", () => {
  it("the face holds no editable control", () => {
    const { container } = draw();
    const face = container.querySelector("[data-form-face]");
    expect(face?.querySelectorAll("input, textarea, select, [contenteditable='true']").length).toBe(0);
  });

  it("thumbnails show the diagnostic count and a Missing placeholder", () => {
    draw();
    expect(document.querySelector('[data-diagnostics="2"]')).toBeTruthy();
    expect(screen.getByText("Missing")).toBeTruthy();
  });

  it("Go to pages to the diagnostic's page", () => {
    const onPage = vi.fn();
    draw({ onPage });
    fireEvent.click(screen.getByText("Go to"));
    expect(onPage).toHaveBeenCalledWith(6);
  });

  it("the total row shows the server's state, never a sum", () => {
    draw();
    expect(document.querySelector('[data-total="off"]')?.textContent).toContain("off 6,200");
    cleanup();
    draw({ total: { state: "tie" } });
    expect(document.querySelector('[data-total="tie"]')?.textContent).toContain("tie");
  });

  it("loading draws the skeleton", () => {
    draw({ loading: true });
    expect(screen.getByLabelText("Rendering the form")).toBeTruthy();
  });
});
