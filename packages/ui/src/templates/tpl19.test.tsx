import { cleanup, render, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TPL07_REQUESTS } from "../specimens/requests";
import { TPL19_COPY, Tpl19Specimen } from "../specimens/tpl19";

// F-06-T10 acceptance: "Frames 1, 2 and 7 render at 390 by 844 with the 56 px firm header and
// 64 px tab bar, open requests match TPL-07, and no Accrued mark or blue appears."

afterEach(cleanup);

function frame(container: HTMLElement, id: string): HTMLElement {
  const board = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (board === null) throw new Error(`no artboard ${id}`);
  return board;
}

describe("TPL-19 frames 1, 2 and 7", () => {
  it("each renders at 390 × 844 with the 56 header and the 64 tab bar", () => {
    const { container } = render(<Tpl19Specimen />);
    for (const id of ["tpl-19-1", "tpl-19-2", "tpl-19-7"]) {
      const board = frame(container, id);
      const phone = board.querySelector<HTMLElement>('[data-variant="portal-mobile"]');
      expect(phone?.className).toContain("w-[390px]");
      expect(phone?.style.height).toBe("844px");
      expect(board.querySelector('[data-shell="mobile-header"]')?.className).toContain("h-[56px]");
      expect(board.querySelector('[data-shell="mobile-tab-bar"]')?.className).toContain(
        "h-[64px]",
      );
    }
  });

  it("1: the greeting, the return card, the to-dos and the team", () => {
    const { container } = render(<Tpl19Specimen />);
    const home = within(frame(container, "tpl-19-1"));
    expect(home.getByRole("heading", { name: "Good morning, Claire" })).toBeTruthy();
    expect(home.getByRole("progressbar", { name: "We're reviewing your return" })).toBeTruthy();
    expect(
      home.getByText("2 documents still needed · extended due date Oct 15, 2026"),
    ).toBeTruthy();
    expect(home.getByText("Upload 2 documents")).toBeTruthy();
    expect(home.getByText("1 new message from Kevin Osei")).toBeTruthy();
    for (const p of TPL19_COPY.team.people) expect(home.getByText(p.name)).toBeTruthy();
  });

  it("2: the open requests are TPL-07's, the rest folded into one row", () => {
    const { container } = render(<Tpl19Specimen />);
    const docs = frame(container, "tpl-19-2");
    const open = TPL07_REQUESTS.filter((r) => r.st === "req").map((r) => r.id);
    const shown = Array.from(docs.querySelectorAll("[data-request]")).map((el) =>
      el.getAttribute("data-request"),
    );
    expect(shown).toEqual(open);
    expect(within(docs).getByText("2 to do")).toBeTruthy();
    expect(
      within(docs).getByText("Photos of multi-page documents are combined into one PDF"),
    ).toBeTruthy();
    expect(within(docs).getByText("4 received · 1 provided by Brightwater Hale")).toBeTruthy();
  });

  it("7: the More sheet holds no Approvals for a household", () => {
    const { container } = render(<Tpl19Specimen />);
    const sheet = frame(container, "tpl-19-7").querySelector<HTMLElement>(
      '[data-shell="more-sheet"]',
    );
    expect(sheet).not.toBeNull();
    const items = within(sheet as HTMLElement)
      .getAllByRole("menuitem")
      .map((i) => i.textContent);
    expect(items).toEqual(["Questions", "Deliverables"]);
  });

  it("shows no product mark and no blue", () => {
    const { container } = render(<Tpl19Specimen />);
    expect(container.textContent).not.toMatch(/Accrued/u);
    expect(container.innerHTML).not.toMatch(/blue|#6A98E8/iu);
  });
});
