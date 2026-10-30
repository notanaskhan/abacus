import { cleanup, fireEvent, render, within } from "@testing-library/react";
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

// F-06-T11 acceptance: "Frame 6 moves the title pill from 2 to do to 1 to do with the green-ink
// receipt, deferred frames render a Deferred (DEC-97) placeholder, and TPL-19 is parity-locked"
// (the lock is Tier D: apps/web/e2e/visual/tier-d-tpl19.spec.ts).
describe("TPL-19 frames 3 to 6, 8 and permission off", () => {
  it("3, 4, 8 and permission off render the Deferred (DEC-97) placeholder", () => {
    const { container } = render(<Tpl19Specimen />);
    for (const id of ["tpl-19-3", "tpl-19-4", "tpl-19-8", "tpl-19-perm"]) {
      expect(frame(container, id).querySelector('[data-capture="deferred"]')?.textContent).toBe(
        "Deferred (DEC-97)",
      );
    }
  });

  it("3 to 6 carry the alternate-path caption", () => {
    const { container } = render(<Tpl19Specimen />);
    for (const id of ["tpl-19-3", "tpl-19-4", "tpl-19-5", "tpl-19-6"]) {
      expect(frame(container, id).textContent).toContain(TPL19_COPY.alternate);
    }
    expect(frame(container, "tpl-19-1").textContent).not.toContain(TPL19_COPY.alternate);
  });

  it("5: two pages, the stitched file, the request picker and Upload", () => {
    const { container } = render(<Tpl19Specimen />);
    const sheet = within(frame(container, "tpl-19-5")).getByRole("dialog", {
      name: "Review & assign",
    });
    expect(sheet.querySelectorAll("[data-page]")).toHaveLength(2);
    expect(
      within(sheet).getByText("Claire_Feld_2025_1095-C_MercerHill.pdf · 2 pages · 3.1 MB"),
    ).toBeTruthy();
    expect(
      within(sheet).getByText(
        "Combined from Claire_Feld_1095C_Camera_P1.jpg and Claire_Feld_1095C_Camera_P2.jpg",
      ),
    ).toBeTruthy();
    expect(within(sheet).getByRole("button", { name: "Retake page 2" })).toBeTruthy();
    expect(within(sheet).getByRole("button", { name: "Add a page" })).toBeTruthy();
    const picker = within(sheet).getByRole("combobox", { name: "Add to request" });
    const options = Array.from((picker as HTMLSelectElement).options).map((o) => o.text);
    expect(options).toEqual([
      "Form 1095-C From Mercer Hill Health",
      "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
      "Something else",
    ]);
    expect((picker as HTMLSelectElement).value).toBe("aca");
    expect(within(sheet).getByRole("button", { name: "Upload" })).toBeTruthy();
  });

  it("6 in flight: the 1095-C card shows the UploadRing at 70%", () => {
    const { container } = render(<Tpl19Specimen />);
    const card = frame(container, "tpl-19-6-ring").querySelector<HTMLElement>(
      '[data-request="aca"]',
    );
    expect(
      within(card as HTMLElement).getByRole("progressbar", { name: /^Uploading/u }),
    ).toBeTruthy();
    expect(within(card as HTMLElement).queryByRole("button", { name: /Upload…/u })).toBeNull();
  });

  it("6: the receipt in green ink and the pill moves from 2 to do to 1 to do", () => {
    const { container } = render(<Tpl19Specimen />);
    expect(within(frame(container, "tpl-19-2")).getByText("2 to do")).toBeTruthy();
    const done = frame(container, "tpl-19-6");
    expect(within(done).getByText("1 to do")).toBeTruthy();
    const receipt = within(done).getByText("You uploaded Sep 14");
    expect(receipt.className).toContain("text-green-ink");
    expect(within(done).getByText("Matched to this request")).toBeTruthy();
  });
});

describe("TPL-19 capture flow on frame 2", () => {
  it("Upload… opens the action sheet; a photo opens Review & assign; Upload lands the receipt", () => {
    const { container } = render(<Tpl19Specimen />);
    const docs = frame(container, "tpl-19-2");
    fireEvent.click(
      within(docs).getByRole("button", { name: "Upload… Form 1095-C From Mercer Hill Health" }),
    );
    const sheet = within(docs).getByRole("dialog", { name: /Upload…/u });
    const camera = sheet.querySelector<HTMLInputElement>('[data-capture-input="camera"]');
    expect(camera?.getAttribute("capture")).toBe("environment");
    expect(camera?.getAttribute("accept")).toBe("image/*");
    const pages = [
      new File(["p1"], "p1.jpg", { type: "image/jpeg" }),
      new File(["p2"], "p2.jpg", { type: "image/jpeg" }),
    ];
    URL.createObjectURL = () => "blob:page";
    fireEvent.change(camera as HTMLInputElement, { target: { files: pages } });
    const review = within(docs).getByRole("dialog", { name: "Review & assign" });
    fireEvent.click(within(review).getByRole("button", { name: "Upload" }));
    expect(within(docs).getByText("1 to do")).toBeTruthy();
    expect(within(docs).getByText("You uploaded Sep 14")).toBeTruthy();
  });
});
