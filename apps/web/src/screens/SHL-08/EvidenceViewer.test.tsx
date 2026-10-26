// P-03-T14: the SHL-08 EvidenceViewer on its two hosts, from the fixture scenarios through the
// generated client. Row acceptance: "The lit figure row and page region share one match, the
// region scrolls to 30% from the top, and no raw file, pdf.js or toolbar Download ever appears."
// Plus P-03 AC3.1–AC3.7 for the states this row builds (a, b, e, f, h).
import { client } from "@abacus/api-client/client";
import { LIT_AT, litScrollTop } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import {
  VIEWER_OVERLAY,
  decodeRef,
  encodeRef,
  sourceViewerArgs,
  sourceViewerTarget,
} from "../../app-core/overlays";
import {
  ALSO_CITED,
  HOVERED_2045,
  K1_STATEMENT,
  K1_STACK,
  TOTAL_INVESTMENTS_CITATION,
} from "../../fixtures/seed/trust";
import { renderRoutes } from "../../testing/support";
import { SHL08 } from "./artboard";
import { AUTO_HIGHLIGHT_KEY, alsoCitedLine } from "./EvidenceViewer";
import { figureValue } from "./LinkedFigures";
import { OPENS, type Shl08State, scenarios } from "./scenarios";
import { textOnly } from "../../fixtures/scenarios/SHL-08";
import { TEXT_VIEW } from "../../app-core/masked-text";
import { PROCESSING_POLL_MS, pollWhileProcessing } from "./useViewerManifest";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  try {
    window.localStorage.removeItem(AUTO_HIGHLIGHT_KEY);
  } catch {
    // no storage in this environment
  }
});

function show(state: Shl08State): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([{ path: "/", component: () => <SHL08 state={state} /> }]);
}

/** Open a ⋯ menu as the kit's own tests do: focus the trigger, then ArrowDown. */
function openMenu(name: string): void {
  const trigger = screen.getByRole("button", { name });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
}

const litOf = (kind: string): HTMLElement[] =>
  Array.from(document.querySelectorAll<HTMLElement>(`[data-match-kind="${kind}"][data-lit]`));

async function regionsDrawn(): Promise<void> {
  await waitFor(
    () => {
      expect(document.querySelectorAll('[data-match-kind="region"]').length).toBeGreaterThan(0);
    },
    { timeout: 4000 },
  );
}

describe("SHL-08a: the drawer opened on box 18A", () => {
  it("the lit figure row and the lit page region share one match", async () => {
    show("a");
    await regionsDrawn();
    await waitFor(() => {
      expect(litOf("row")).toHaveLength(1);
      expect(litOf("region")).toHaveLength(1);
    });
    const row = litOf("row")[0];
    const region = litOf("region")[0];
    expect(row?.getAttribute("data-match")).toBe(OPENS.a.matchId);
    expect(region?.getAttribute("data-match")).toBe(row?.getAttribute("data-match"));
    expect(row?.textContent).toBe("Tax-exempt interest income (box 18A)$1,550");
  });

  it("the card lists the verified figures in page order, titled by the figure", async () => {
    show("a");
    const card = await screen.findByRole("region", { name: "Linked figure · Form 1040 line 2a" });
    await waitFor(() => {
      expect(within(card).getAllByRole("button", { name: /\$|IL/ })).toHaveLength(4);
    });
    const rows = Array.from(card.querySelectorAll("li")).map((li) => li.textContent);
    expect(rows).toEqual([
      "Net rental real estate income (box 2)$307,900",
      "Interest income (box 5)$4,600",
      "Tax-exempt interest income (box 18A)$1,550",
      "StatesIL / CO / NY",
    ]);
    expect(within(card).getByText("Source 1 of 3")).toBeTruthy();
  });

  it("the region carries the floating tag, the stack peeks twice, and Also cited reads the stack", async () => {
    show("a");
    await regionsDrawn();
    await waitFor(() => {
      expect(document.querySelector("[data-linked-figure]")?.textContent).toBe(
        "Form 1040 · line 2a1,550",
      );
    });
    expect(document.querySelector("[data-stack]")?.getAttribute("data-stack")).toBe("2");
    expect(document.querySelectorAll("[data-stack-edge]")).toHaveLength(2);
    expect(document.querySelector("[data-also-cited]")?.textContent).toBe(ALSO_CITED);
  });

  it("hovering another figure row lights its region instead", async () => {
    show("a");
    await regionsDrawn();
    const row = await screen.findByRole("button", { name: /Interest income \(box 5\)/ });
    fireEvent.pointerEnter(row);
    await waitFor(() => {
      expect(litOf("region")[0]?.getAttribute("data-match")).toBe(row.getAttribute("data-match"));
    });
  });

  it("no toolbar Download, no raw file: Download and Open in Files live only in the ⋯ menu", async () => {
    show("a");
    await regionsDrawn();
    const bar = screen.getByRole("toolbar", { name: "Viewer" });
    expect(bar.textContent).not.toMatch(/download/i);
    expect(
      within(bar)
        .getAllByRole("button")
        .map((b) => b.getAttribute("aria-label")),
    ).not.toContain("Download");
    expect(document.querySelectorAll("iframe, object, embed, canvas")).toHaveLength(0);
    await waitFor(() => {
      expect(document.querySelectorAll("img").length).toBeGreaterThan(0);
    });
    for (const img of Array.from(document.querySelectorAll("img"))) {
      expect(img.getAttribute("src")).toMatch(/^blob:/);
    }
    expect(document.body.textContent).not.toMatch(/pdf\.js/i);
    openMenu("More actions");
    const menu = await screen.findByRole("menu");
    expect(menu.textContent).toContain("Download");
    expect(menu.textContent).toContain("Open in Files");
    expect(menu.textContent).toContain("Auto-highlight cited fields");
  });

  it("the masks stay their tokens", async () => {
    show("a");
    await waitFor(() => {
      expect(document.body.textContent).toContain("•••-••-4417");
    });
    expect(document.body.textContent).toContain("••-•••0287");
  });
});

describe("SHL-08f: source 2 of 3", () => {
  it("opens on the K-1 statement, p. 3, with its line lit", async () => {
    show("f");
    await screen.findByText("Source 2 of 3");
    await regionsDrawn();
    expect(document.body.textContent).toContain("Ridgeline 2025 K-1 statement.pdf");
    await waitFor(() => {
      expect(litOf("region")[0]?.getAttribute("data-match")).toBe(K1_STACK[1]?.match_id);
    });
  });

  it("‹ steps back to the draft K-1 with box 18A lit, and › comes back", async () => {
    show("f");
    await screen.findByText("Source 2 of 3");
    fireEvent.click(screen.getByRole("button", { name: "Previous source" }));
    await screen.findByText("Source 1 of 3");
    await waitFor(() => {
      expect(document.body.textContent).toContain("Ridgeline_2025_K1_JonahFeld_DRAFT.pdf");
      expect(litOf("region")[0]?.getAttribute("data-match")).toBe(K1_STACK[0]?.match_id);
    });
    fireEvent.click(screen.getByRole("button", { name: "Next source" }));
    await screen.findByText("Source 2 of 3");
    await waitFor(() => {
      expect(document.body.textContent).toContain("Ridgeline 2025 K-1 statement.pdf");
    });
    expect(OPENS.f.versionId).toBe(K1_STATEMENT);
  });
});

describe("SHL-08e: loading", () => {
  it("three pulsing skeleton pages, the Processing… pill, busy, and no page image", async () => {
    show("e");
    await screen.findByText("Processing…");
    const well = document.querySelector("[data-viewer-well]");
    expect(well?.getAttribute("aria-busy")).toBe("true");
    expect(well?.children).toHaveLength(3);
    expect(document.querySelectorAll("img")).toHaveLength(0);
    expect(document.body.textContent).toContain("Ridgeline_2025_K1_JonahFeld_DRAFT.pdf");
  });

  it("polls a processing manifest every 3 s and stops once it is not", () => {
    expect(PROCESSING_POLL_MS).toBe(3000);
    const base = { status: "processing" } as Parameters<typeof pollWhileProcessing>[0];
    expect(pollWhileProcessing(base)).toBe(3000);
    expect(pollWhileProcessing(undefined)).toBe(false);
    expect(pollWhileProcessing({ ...base, status: "ready" } as typeof base)).toBe(false);
  });
});

describe("SHL-08h: auto-highlight", () => {
  it("outlines every cited region but the hovered one, which is lit", async () => {
    show("h");
    await regionsDrawn();
    await waitFor(() => {
      expect(litOf("region")[0]?.getAttribute("data-match")).toBe(HOVERED_2045.match_id);
    });
    expect(document.querySelectorAll("[data-outlined]")).toHaveLength(8);
  });

  it("⋯ Auto-highlight cited fields off removes the outlines and is remembered", async () => {
    show("h");
    await regionsDrawn();
    await waitFor(() => {
      expect(document.querySelectorAll("[data-outlined]").length).toBeGreaterThan(0);
    });
    openMenu("More actions");
    const menu = await screen.findByRole("menu");
    const toggle = within(menu).getByText("Auto-highlight cited fields").closest("[role]");
    if (!(toggle instanceof HTMLElement)) throw new Error("no auto-highlight item");
    fireEvent.click(toggle);
    await waitFor(() => {
      expect(document.querySelectorAll("[data-outlined]")).toHaveLength(0);
    });
    expect(window.localStorage.getItem(AUTO_HIGHLIGHT_KEY)).toBe("off");
  });
});

describe("SHL-08b: the dock pane", () => {
  it("Agent · Viewer · Notes with Viewer on, the evidence bar on page 2 of 3, the total lit", async () => {
    show("b");
    const dock = await screen.findByRole("complementary", { name: "Dock" });
    expect(within(dock).getByRole("tab", { name: "Viewer" }).getAttribute("aria-selected")).toBe(
      "true",
    );
    await regionsDrawn();
    await waitFor(() => {
      expect(litOf("region")[0]?.getAttribute("data-match")).toBe(
        TOTAL_INVESTMENTS_CITATION.match_id,
      );
    });
    const bar = dock.querySelector('[data-viewer-bar="evidence"]');
    expect(bar?.textContent).toContain("2 / 3");
    expect(bar?.textContent).not.toMatch(/download/i);
  });

  it("clicking another trial-balance row re-targets the viewer without closing it", async () => {
    show("b");
    await regionsDrawn();
    fireEvent.click(await screen.findByRole("button", { name: "KRS Target 2045 Fund" }));
    await waitFor(() => {
      expect(litOf("region")[0]?.getAttribute("data-match")).toBe(HOVERED_2045.match_id);
    });
    expect(screen.getByRole("complementary", { name: "Dock" })).toBeTruthy();
  });

  it("the trial balance foots: 16,500,000.00 + 312,400.00 = 16,812,400.00", async () => {
    show("b");
    await screen.findByText("Total investments at fair value");
    expect(screen.getByText("16,812,400.00")).toBeTruthy();
  });
});

describe("the 30% rule and the overlay", () => {
  it("a lit region comes to rest 30% from the well's top", () => {
    expect(LIT_AT).toBe(0.3);
    // The well's top is at 100 and it is 600 high; the region's top is 700 down the viewport.
    expect(litScrollTop(0, 100, 600, 700)).toBe(420);
    expect(litScrollTop(420, 100, 600, 280)).toBe(420);
    expect(litScrollTop(0, 100, 600, 150)).toBe(0);
  });

  it("?ov=viewer carries the version, the match and the opening anchor through the codec", () => {
    const target = {
      evidenceVersionId: "v-1",
      matchId: "ev:v-1#p1:372,612,568,632",
      anchor: { type: "tax_form_line", id: "line-1", ref: "line_2a" },
      figure: "Form 1040 line 2a",
      engagementId: "e-1",
    };
    const encoded = encodeRef({ key: VIEWER_OVERLAY, args: sourceViewerArgs(target) });
    const decoded = decodeRef(encoded);
    expect(decoded?.key).toBe("viewer");
    expect(sourceViewerTarget(decoded?.args ?? [])).toEqual(target);
    expect(sourceViewerArgs({ evidenceVersionId: "v-1" })).toEqual(["v-1"]);
    expect(sourceViewerTarget(["v-1"])).toEqual({
      evidenceVersionId: "v-1",
      matchId: null,
      anchor: null,
      figure: null,
      engagementId: null,
    });
    expect(sourceViewerArgs({ evidenceVersionId: "v-1", engagementId: "e-1" })).toEqual([
      "v-1",
      "",
      "",
      "",
      "",
      "",
      "e-1",
    ]);
    expect(sourceViewerTarget([])).toBeUndefined();
  });

  it("Also cited lists the other stack members; figures read as money only when numeric", () => {
    expect(alsoCitedLine(K1_STACK, 0)).toBe(ALSO_CITED);
    expect(alsoCitedLine(K1_STACK.slice(0, 1), 0)).toBeNull();
    expect(figureValue("307,900")).toBe("$307,900");
    expect(figureValue("IL / CO / NY")).toBe("IL / CO / NY");
  });
});

describe("DEC-369: the text view an offshore reader gets (no page images until OCR)", () => {
  it("renders the masked text the server gives and never a page image or a region", async () => {
    restore = installFixtureMode(textOnly("c"));
    renderRoutes([{ path: "/", component: () => <SHL08 state="c" /> }]);
    await waitFor(() => {
      expect(screen.getByText(TEXT_VIEW.note)).toBeTruthy();
      expect(screen.getByText(/•••-••-6081/)).toBeTruthy();
    });
    expect(screen.getByText(TEXT_VIEW.page(1))).toBeTruthy();
    expect(document.querySelectorAll("img")).toHaveLength(0);
    expect(document.querySelectorAll('[data-match-kind="region"]')).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/\d{3}-\d{2}-\d{4}/);
  });

  it("the images view is unchanged for the same version read onshore", async () => {
    show("c");
    await regionsDrawn();
    expect(screen.queryByText(TEXT_VIEW.note)).toBeNull();
  });
});
