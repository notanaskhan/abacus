import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { FELD_FILE, HARBORLINE_FILE, SourceViewerSpecimen } from "../specimens/viewer";
import { installDomShims } from "../test-dom";
import { MatchScope } from "../tracing/match";
import { createMatchStore } from "../tracing/match-store";
import type { CitationPayload } from "../tracing/types";
import { LIT_AT, SourceViewer, VIEWER_ZOOM, litScrollTop, pageSrcAllowed } from "./source-viewer";

// F-05-T47 (builder tests): "Pages render only server page images (no pdf.js, no SheetJS, no raw
// file), regions stay invisible until lit, and Download is absent from the bar." Plus zoom, paging,
// rotate, Find, the linked figure tag and its flip, the evidence bar and the status words. The
// independent acceptance tests are e5-acceptance.test.tsx (F-05-T48).

beforeAll(installDomShims);
afterEach(cleanup);

describe("page sources", () => {
  it("allow same-origin paths, blobs and PNG data only", () => {
    expect(pageSrcAllowed("/v1/evidence-versions/x/pages/1")).toBe(true);
    expect(pageSrcAllowed("blob:https://app/1")).toBe(true);
    expect(pageSrcAllowed("data:image/png;base64,iVBORw0KGgo=")).toBe(true);
    expect(pageSrcAllowed("//evil.example/p.png")).toBe(false);
    expect(pageSrcAllowed("https://evil.example/p.png")).toBe(false);
    expect(pageSrcAllowed("data:image/svg+xml;base64,PHN2Zz4=")).toBe(false);
    expect(pageSrcAllowed("data:application/pdf;base64,JVBERi0=")).toBe(false);
    expect(pageSrcAllowed("javascript:alert(1)")).toBe(false);
  });
});

describe("full variant", () => {
  it("draws one img per page and nothing else of the file", () => {
    const { container } = render(<SourceViewer file={FELD_FILE} />);
    const imgs = container.querySelectorAll("img");
    expect(imgs).toHaveLength(2);
    expect(imgs[0]?.getAttribute("alt")).toBe("Page 1 of 2");
    expect(container.querySelectorAll("iframe, object, embed, canvas")).toHaveLength(0);
  });

  it("the bar has zoom, Fit, rotate, paging, the swatch and Find, and never Download", () => {
    render(<SourceViewer file={FELD_FILE} menu={[{ label: "Download", onSelect: vi.fn() }]} />);
    const bar = screen.getByRole("toolbar", { name: "Viewer" });
    const names = within(bar)
      .getAllByRole("button")
      .map((b) => b.getAttribute("aria-label"));
    expect(names).toEqual([
      "Zoom out",
      "Fit to width",
      "Zoom in",
      "Rotate",
      "Previous page",
      "Next page",
      "Highlight colour",
      "Find in document",
    ]);
    expect(bar.textContent).not.toMatch(/download/i);
  });

  it("zoom steps by 25% between 50% and 200%; Fit resets", () => {
    render(<SourceViewer file={FELD_FILE} />);
    const zoomIn = screen.getByRole("button", { name: "Zoom in" });
    fireEvent.click(zoomIn);
    expect(screen.getByRole("button", { name: "Fit to width" }).textContent).toBe("125%");
    for (let i = 0; i < 6; i += 1) fireEvent.click(zoomIn);
    expect(screen.getByRole("button", { name: "Fit to width" }).textContent).toBe(
      `${String(VIEWER_ZOOM.max * 100)}%`,
    );
    expect((zoomIn as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Fit to width" }));
    expect(screen.getByRole("button", { name: "Fit to width" }).textContent).toBe("Fit");
  });

  it("paging disables at the ends", () => {
    render(<SourceViewer file={FELD_FILE} />);
    const prev = screen.getByRole<HTMLButtonElement>("button", { name: "Previous page" });
    const next = screen.getByRole<HTMLButtonElement>("button", { name: "Next page" });
    expect(prev.disabled).toBe(true);
    fireEvent.click(next);
    expect(next.disabled).toBe(true);
    expect(prev.disabled).toBe(false);
  });

  it("rotate turns every page 90 degrees per press", () => {
    const { container } = render(<SourceViewer file={FELD_FILE} />);
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    const page = container.querySelector<HTMLElement>('[data-page="1"]');
    expect(page?.style.transform).toBe("rotate(90deg)");
  });
});

describe("regions", () => {
  it("are invisible until lit, then show the linked figure tag", () => {
    vi.useFakeTimers();
    try {
      const store = createMatchStore<CitationPayload>();
      const { container } = render(
        <MatchScope store={store}>
          <SourceViewer file={FELD_FILE} />
        </MatchScope>,
      );
      const region = FELD_FILE.regions[0];
      if (region === undefined) throw new Error("no region");
      const boxes = container.querySelectorAll(`[data-match="${region.match}"]`);
      expect(boxes.length).toBe(2); // box 1a and the statement band
      for (const b of boxes) expect(b.hasAttribute("data-lit")).toBe(false);
      expect(container.querySelector("[data-linked-figure]")).toBeNull();
      act(() => {
        store.togglePin(region.match, null);
      });
      for (const b of boxes) expect(b.hasAttribute("data-lit")).toBe(true);
      const tag = container.querySelector("[data-linked-figure]");
      expect(tag?.textContent).toBe("Form 1040 · Line 3b$4,812");
      expect(container.querySelector("[data-band]")?.hasAttribute("data-lit")).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("the tag flips left when the region's right has less than 170px of room", () => {
    const store = createMatchStore<CitationPayload>();
    const edge = {
      ...FELD_FILE,
      regions: [
        {
          match: FELD_FILE.regions[0]?.match ?? ("" as never),
          page: 1,
          rects: [[400, 100, 600, 120]] as const,
          linkedFigure: { label: "L", value: "V" },
        },
      ],
    };
    const { container } = render(
      <MatchScope store={store}>
        <SourceViewer file={edge} pageWidth={400} />
      </MatchScope>,
    );
    act(() => {
      store.togglePin(edge.regions[0]?.match ?? ("" as never), null);
    });
    expect(
      container.querySelector("[data-linked-figure]")?.getAttribute("data-linked-figure"),
    ).toBe("left");
  });

  it("Find pins the first region whose label holds the words", () => {
    const store = createMatchStore<CitationPayload>();
    render(
      <MatchScope store={store}>
        <SourceViewer file={FELD_FILE} />
      </MatchScope>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Find in document" }));
    const input = screen.getByRole("textbox", { name: "Find in document" });
    fireEvent.change(input, { target: { value: "foreign tax" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(store.get()).toMatchObject({ id: FELD_FILE.regions[3]?.match, pinned: true });
  });
});

describe("evidence variant and states", () => {
  it("the evidence bar is left-aligned with the name and no paging arrows", () => {
    const { container } = render(<SourceViewer file={HARBORLINE_FILE} variant="evidence" />);
    const bar = container.querySelector('[data-viewer-bar="evidence"]');
    expect(bar?.textContent).toContain("Harborline Net Trust Assets 12-31-2025.pdf");
    expect(bar?.textContent).toContain("1 / 3");
    expect(screen.queryByRole("button", { name: "Next page" })).toBeNull();
  });

  it("each status reads its registry word and draws no page", () => {
    for (const [status, word] of [
      ["processing", "Processing…"],
      ["password_protected", "Password-protected"],
      ["not_previewable", "Can't preview"],
    ] as const) {
      const { container, unmount } = render(
        <SourceViewer file={HARBORLINE_FILE} status={status} />,
      );
      expect(screen.getByRole("status").textContent).toBe(word);
      expect(container.querySelectorAll("img")).toHaveLength(0);
      unmount();
    }
  });

  it("loading draws skeleton pages and is busy", () => {
    const { container } = render(<SourceViewer file={HARBORLINE_FILE} loading />);
    expect(container.querySelector("[data-viewer-well]")?.getAttribute("aria-busy")).toBe("true");
    expect(container.querySelectorAll("img")).toHaveLength(0);
  });
});

describe("the specimen", () => {
  it("hovering a tree leaf lights the region, the worksheet line and the file chip together", () => {
    vi.useFakeTimers();
    try {
      const { container } = render(<SourceViewerSpecimen />);
      const full = container.querySelector<HTMLElement>('[data-viewer-specimen="full"]');
      if (full === null) throw new Error("no full specimen");
      fireEvent.pointerEnter(within(full).getByRole("button", { name: "Ordinary dividends 1a" }));
      act(() => {
        vi.advanceTimersByTime(130);
      });
      expect(full.querySelectorAll("[data-lit]").length).toBeGreaterThanOrEqual(4);
      expect(full.querySelector("[data-file-chip]")?.hasAttribute("data-lit")).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });
});

// P-03-T14 (SHL-08): what the EvidenceViewer asks of the shell: the lit region scrolled to 30% from
// the well's top, auto-highlight outlines, the multi-source stack edges, three skeletons, and a
// page whose image is still loading drawn blank with its regions.
describe("SHL-08 slots", () => {
  const cited = {
    ...HARBORLINE_FILE,
    regions: HARBORLINE_FILE.regions.map((r) => ({ ...r, cited: true })),
  };

  it("scrollToLit brings the lit region to 30% from the well's top and moves the page count", () => {
    const region = HARBORLINE_FILE.regions[0];
    if (region === undefined) throw new Error("no region");
    const store = createMatchStore<CitationPayload>();
    const rect = vi
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockImplementation(function (this: HTMLElement) {
        const top = this.hasAttribute("data-viewer-well")
          ? 100
          : this.getAttribute("data-match") === region.match
            ? 900
            : 0;
        return { top, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: top } as DOMRect;
      });
    const height = vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
    try {
      const { container } = render(
        <MatchScope store={store}>
          <SourceViewer file={HARBORLINE_FILE} scrollToLit />
        </MatchScope>,
      );
      act(() => {
        store.light(region.match, null);
      });
      const well = container.querySelector<HTMLElement>("[data-viewer-well]");
      expect(well?.scrollTop).toBe(900 - 100 - LIT_AT * 600);
      expect(screen.getByRole("toolbar", { name: "Viewer" }).textContent).toContain("2 / 3");
    } finally {
      rect.mockRestore();
      height.mockRestore();
    }
  });

  it("litScrollTop never goes above the top", () => {
    expect(litScrollTop(0, 0, 1000, 100)).toBe(0);
    expect(litScrollTop(50, 0, 1000, 400)).toBe(150);
  });

  it("outlineCited outlines cited regions until lit; off, nothing is outlined", () => {
    const store = createMatchStore<CitationPayload>();
    const { container, rerender } = render(
      <MatchScope store={store}>
        <SourceViewer file={cited} outlineCited />
      </MatchScope>,
    );
    const count = container.querySelectorAll('[data-match-kind="region"]').length;
    expect(container.querySelectorAll("[data-outlined]")).toHaveLength(count);
    const first = cited.regions[0];
    if (first === undefined) throw new Error("no region");
    act(() => {
      store.light(first.match, null);
    });
    expect(container.querySelectorAll("[data-outlined]").length).toBe(count - first.rects.length);
    rerender(
      <MatchScope store={store}>
        <SourceViewer file={cited} />
      </MatchScope>,
    );
    expect(container.querySelectorAll("[data-outlined]")).toHaveLength(0);
  });

  it("stack draws its edges under the page holding the match, with the band level with it", () => {
    const first = cited.regions[0];
    if (first === undefined) throw new Error("no region");
    const { container } = render(
      <SourceViewer file={cited} stack={{ match: first.match, edges: 2 }} />,
    );
    const stack = container.querySelector("[data-stack]");
    expect(stack?.getAttribute("data-stack")).toBe("2");
    expect(stack?.querySelector(`[data-page="${String(first.page)}"]`)).not.toBeNull();
    expect(container.querySelectorAll("[data-stack-edge]")).toHaveLength(2);
  });

  it("three skeletons when asked, and a pending page draws blank with its regions", () => {
    const { container, unmount } = render(
      <SourceViewer file={HARBORLINE_FILE} loading skeletons={3} />,
    );
    expect(container.querySelector("[data-viewer-well]")?.children).toHaveLength(3);
    unmount();
    const pending = {
      ...HARBORLINE_FILE,
      pages: HARBORLINE_FILE.pages.map((p) => ({ ...p, src: "" })),
    };
    const next = render(<SourceViewer file={pending} />);
    expect(next.container.querySelectorAll("img")).toHaveLength(0);
    expect(next.container.querySelectorAll('[data-match-kind="region"]').length).toBeGreaterThan(
      0,
    );
    expect(next.container.textContent).not.toContain("Can't preview");
  });

  it("header={false} drops the name header but keeps the toolbar", () => {
    render(<SourceViewer file={HARBORLINE_FILE} header={false} />);
    expect(screen.queryByRole("heading", { name: HARBORLINE_FILE.name })).toBeNull();
    expect(screen.getByRole("toolbar", { name: "Viewer" })).toBeTruthy();
  });
});
