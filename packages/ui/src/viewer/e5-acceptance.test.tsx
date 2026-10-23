import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import {
  type MatchId,
  MatchScope,
  type RevealSlot,
  SourceViewer,
  type ViewerFile,
  matchIdOf,
} from "../index";

// F-05-T48: independent acceptance tests (ADR-078) for E5, the SourceViewer shell, written from the
// ACs through the package's public exports only:
//   F-05-T48  "No client bytes reach the DOM as HTML, reveal fires its logged callback once per
//              explicit click, and every viewer state is axe clean." (axe: e2e/viewer.spec.ts)
//   F-05 G3   "Pages are server-rendered images ... no pdf.js, SheetJS or raw client file ever
//              renders in the browser (ADR-052) ... when 'Reveal (logged)' is clicked, then the
//              shell calls the supplied reveal callback exactly once per click."
// Client strings (file names, region labels, mask tokens, revealed values) are hostile (ADR-052,
// ADR-064): each case below hands the shell markup and expects it back as text.

beforeAll(installDomShims);
afterEach(cleanup);

const HOSTILE =
  '<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script><b>bold</b>';
const PNG = "data:image/png;base64,iVBORw0KGgo=";
const V = "11111111-2222-4333-8444-555555555555";
const MATCH: MatchId = matchIdOf({
  kind: "document_text",
  evidence_version_id: V,
  page: 1,
  bbox: [10, 10, 100, 30],
});

function hostileFile(src = PNG): ViewerFile {
  return {
    name: HOSTILE,
    pages: [{ n: 1, width_pt: 612, height_pt: 792, rotation: 0, src }],
    regions: [
      {
        match: MATCH,
        page: 1,
        rects: [[10, 10, 100, 30]],
        label: HOSTILE,
        linkedFigure: { label: HOSTILE, value: HOSTILE },
      },
    ],
    masks: [{ id: "m1", page: 1, rect: [10, 40, 100, 60], kind: "ssn", display: HOSTILE }],
  };
}

function injected(root: HTMLElement): Element[] {
  return [...root.querySelectorAll("script, b, iframe, object, embed, img[onerror], [onerror]")];
}

describe("no client bytes reach the DOM as HTML", () => {
  it("file name, mask token and region label render as text, in both variants", () => {
    for (const variant of ["full", "evidence"] as const) {
      const { container, unmount } = render(
        <SourceViewer file={hostileFile()} variant={variant} />,
      );
      expect(injected(container)).toEqual([]);
      expect(container.textContent).toContain(HOSTILE);
      expect((window as { __pwned?: number }).__pwned).toBeUndefined();
      unmount();
    }
  });

  it("a lit region's linked figure renders its label and value as text", () => {
    const { container } = render(
      <MatchScope>
        <SourceViewer file={hostileFile()} />
      </MatchScope>,
    );
    const region = container.querySelector(`[data-match="${MATCH}"]`);
    if (region === null) throw new Error("no region");
    fireEvent.click(region);
    expect(container.textContent.split(HOSTILE).length).toBeGreaterThanOrEqual(4);
    expect(injected(container)).toEqual([]);
  });

  it("a revealed value and its note render as text", () => {
    const reveal: RevealSlot = {
      allowed: true,
      onReveal: vi.fn(),
      revealed: { m1: { value: HOSTILE, note: HOSTILE } },
    };
    const { container } = render(<SourceViewer file={hostileFile()} reveal={reveal} />);
    expect(injected(container)).toEqual([]);
    expect(container.querySelector("[data-reveal-note]")?.textContent).toBe(HOSTILE);
  });

  it("only server page images render: no other source reaches an img, and nothing embeds the file", () => {
    for (const src of [
      "https://cdn.example/raw.pdf",
      "//evil.example/page.png",
      "javascript:alert(1)",
      "data:text/html;base64,PHNjcmlwdD4=",
      "data:image/svg+xml;base64,PHN2Zz4=",
      "data:application/pdf;base64,JVBERi0xLjc=",
    ]) {
      const { container, unmount } = render(<SourceViewer file={hostileFile(src)} />);
      expect(container.querySelectorAll("img"), src).toHaveLength(0);
      expect(container.querySelectorAll("iframe, object, embed, canvas"), src).toHaveLength(0);
      unmount();
    }
    const { container } = render(
      <SourceViewer file={hostileFile("/v1/evidence-versions/x/pages/1")} />,
    );
    expect(container.querySelector("img")?.getAttribute("src")).toBe(
      "/v1/evidence-versions/x/pages/1",
    );
  });

  it("Download is never in a bar, whatever the menu holds", () => {
    for (const variant of ["full", "evidence"] as const) {
      const { container, unmount } = render(
        <SourceViewer
          file={hostileFile()}
          variant={variant}
          menu={[{ label: "Download", onSelect: vi.fn() }]}
        />,
      );
      const bar = container.querySelector("[data-viewer-bar]");
      expect(bar).not.toBeNull();
      const buttons = within(bar as HTMLElement).queryAllByRole("button");
      expect(
        buttons.map((b) => b.textContent + (b.getAttribute("aria-label") ?? "")),
      ).not.toContainEqual(expect.stringMatching(/download/i));
      unmount();
    }
  });
});

describe("the logged reveal", () => {
  it("fires once per explicit click with the mask's id, and never on render, hover or focus", () => {
    const onReveal = vi.fn();
    render(<SourceViewer file={hostileFile()} reveal={{ allowed: true, onReveal }} />);
    expect(onReveal).not.toHaveBeenCalled();
    const button = screen.getByRole("button", { name: "Reveal (logged)" });
    fireEvent.pointerEnter(button);
    fireEvent.focus(button);
    expect(onReveal).not.toHaveBeenCalled();
    fireEvent.click(button);
    expect(onReveal).toHaveBeenCalledTimes(1);
    expect(onReveal).toHaveBeenLastCalledWith("m1");
    fireEvent.click(button);
    expect(onReveal).toHaveBeenCalledTimes(2);
  });

  it("is not offered without pii.reveal, and only the token shows", () => {
    const onReveal = vi.fn();
    const { container } = render(
      <SourceViewer file={hostileFile()} reveal={{ allowed: false, onReveal }} />,
    );
    expect(screen.queryByRole("button", { name: "Reveal (logged)" })).toBeNull();
    expect(container.querySelector("[data-mask]")?.textContent).toBe(HOSTILE);
  });

  it("once revealed, the value replaces the token and the control is gone", () => {
    render(
      <SourceViewer
        file={{
          ...hostileFile(),
          masks: [
            { id: "m1", page: 1, rect: [10, 40, 100, 60], kind: "ssn", display: "•••-••-6081" },
          ],
        }}
        reveal={{
          allowed: true,
          onReveal: vi.fn(),
          revealed: {
            m1: {
              value: "000-00-6081",
              note: "Revealed by Samuel Ito · 9:31 AM · logged to the audit trail",
            },
          },
        }}
      />,
    );
    expect(screen.queryByText("•••-••-6081")).toBeNull();
    expect(screen.getByText("000-00-6081")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Reveal (logged)" })).toBeNull();
  });
});

describe("regions stay invisible until lit", () => {
  it("an unlit region carries no fill class state and no tag", () => {
    const { container } = render(<SourceViewer file={hostileFile()} />);
    const region = container.querySelector(`[data-match="${MATCH}"]`);
    expect(region?.hasAttribute("data-lit")).toBe(false);
    expect(region?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector("[data-linked-figure]")).toBeNull();
  });
});
