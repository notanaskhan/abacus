// SHL-07 · Citation popover (P-03-T11). One test per artboard (a–e) on its fixture scenario, and
// the task's acceptance: "Hover intent 150 ms previews at 95% opacity, click pins and keeps the
// ring, Escape closes and refocuses the cell, and an unverified citation never renders as fact."
import { type CitationV2Out, type ListPageCitationV2Out } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { MatchScope } from "@abacus/ui";
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type Scenario, installFixtureMode, json } from "../../app-core/fixture-mode";
import { KEYSTONE_CELL, SERVICE_ORGS_WORKPAPER, STEP_CITATION } from "../../fixtures/seed/trust";
import { renderRoutes } from "../../testing/support";
import { SHL07 } from "./artboard";
import { CitationPopoverContainer, CitedCell, HOVER_INTENT_MS, POPOVER_WIDTH } from ".";
import { STATES, type Shl07State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  vi.useRealTimers();
});

function show(state: Shl07State, scenario: Scenario = scenarios[state]): void {
  restore = installFixtureMode(scenario);
  renderRoutes([{ path: "/", component: () => <SHL07 state={state} /> }]);
}

async function card(): Promise<HTMLElement> {
  let found: HTMLElement | null = null;
  await waitFor(
    () => {
      found = document.querySelector<HTMLElement>('[data-cite="card"]');
      expect(found).not.toBeNull();
    },
    { timeout: 2000 },
  );
  return found as unknown as HTMLElement;
}

const popover = (): HTMLElement | null =>
  document.querySelector<HTMLElement>('[data-popover="anchored"]');

describe("SHL-07 artboards", () => {
  it("has a scenario for every artboard, a–e", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e"]);
  });

  it("a: single citation, pinned on Keystone: the step, the doc icon, 1 citation, 372 wide", async () => {
    show("a");
    const found = await card();
    expect(within(found).getByText("BH-EBP-110: General Planning Procedures")).toBeTruthy();
    expect(within(found).getByText(/^4\. Identify each service organization/)).toBeTruthy();
    expect(found.querySelector('[data-cite="footer"]')?.textContent).toBe("1 citation");
    expect(found.hasAttribute("data-pinned")).toBe(true);
    expect(popover()?.style.width).toBe(`${String(POPOVER_WIDTH.citation)}px`);
    const cell = document.querySelector<HTMLElement>("[data-cited]");
    expect(cell?.textContent).toBe("Keystone Retirement Services");
    expect(cell?.hasAttribute("data-lit")).toBe(true); // the cell keeps its ring while pinned
    expect(document.querySelector("[data-cited-row]")).not.toBeNull();
  });

  it("b: the stack steps 1 / 3 → 2 / 3 with the SOC 1 quote, its thumb and ghost edges", async () => {
    show("b");
    const found = await card();
    expect(within(found).getByText("1 / 3")).toBeTruthy();
    expect(found.querySelectorAll("[data-ghost-edge]")).toHaveLength(2);
    expect(found.querySelector('[data-cite="footer"]')?.textContent).toBe("3 citations");
    fireEvent.click(within(found).getByRole("button", { name: "Next source" }));
    const second = await card();
    await waitFor(() => {
      expect(within(second).getByText("2 / 3")).toBeTruthy();
    });
    expect(
      within(second).getByText(
        "Keystone SOC 1 Type 2 report, Oct 1 2024 – Sep 30 2025 · Section I, p. 3",
      ),
    ).toBeTruthy();
    expect(second.textContent).toContain(
      "Keystone provides recordkeeping, loan administration and distribution processing",
    );
    expect(second.querySelector('[data-cite="thumb"]')).not.toBeNull();
    // The cell stays lit while the popover steps through sources.
    expect(document.querySelector("[data-cited]")?.hasAttribute("data-lit")).toBe(true);
  });

  it("c: the guidance is 420 wide, with no doc icon and no footer, as plain program text", async () => {
    show("c");
    const found = await card();
    expect(found.dataset.variant).toBe("guidance");
    expect(popover()?.style.width).toBe(`${String(POPOVER_WIDTH.guidance)}px`);
    expect(found.querySelector('[data-cite="footer"]')).toBeNull();
    expect(found.querySelector('[data-cite="program-text"]')?.textContent).toMatch(
      /^Presumed fraud risks: 1\. Management override of controls/,
    );
    expect(within(found).getByText("Risk Assessment — overall risks and fraud")).toBeTruthy();
  });

  it("d: the hover preview renders at 95% opacity, not pinned; a click pins it", async () => {
    show("d");
    const found = await card();
    expect(found.hasAttribute("data-pinned")).toBe(false);
    expect(found.className).toContain("opacity-95");
    const cell = document.querySelector<HTMLElement>("[data-cited]") as HTMLElement;
    fireEvent.click(cell);
    await waitFor(() => {
      expect(document.querySelector('[data-cite="card"]')?.hasAttribute("data-pinned")).toBe(true);
    });
    expect(cell.hasAttribute("data-lit")).toBe(true);
  });

  it("e: the source moved: the danger line and Re-link…", async () => {
    show("e");
    const found = await card();
    const moved = found.querySelector<HTMLElement>('[data-cite="moved"]');
    expect(moved?.textContent).toBe(
      "Source moved — BH-EBP-110 v2 was superseded by EBP v3 on Jan 1, 2026",
    );
    expect(moved?.className).toContain("text-danger");
    expect(within(found).getByRole("button", { name: "Re-link…" })).toBeTruthy();
  });

  it("e without citation.relink: no Re-link…", async () => {
    const without: CitationV2Out = {
      ...STEP_CITATION,
      state: "moved",
      moved: { successor_ref: "EBP v3", at: "2026-01-01T06:00:00Z" },
      source: { ...STEP_CITATION.source, version: "2" },
      allowed_actions: [],
    };
    show("e", {
      ...scenarios.e,
      handlers: {
        ...scenarios.e.handlers,
        "GET /v1/citations": () =>
          json({ items: [without], total: 1 } satisfies ListPageCitationV2Out),
      },
    });
    const found = await card();
    expect(found.querySelector('[data-cite="moved"]')).not.toBeNull();
    expect(within(found).queryByRole("button", { name: "Re-link…" })).toBeNull();
  });

  it("an unverified citation never renders as fact: Unverified, no quote", async () => {
    const unverified: CitationV2Out = {
      ...STEP_CITATION,
      kind: "document_text",
      verified: false,
      verification_reason: "quote_not_found",
      quote: "Keystone is the plan's recordkeeper.",
      source: { ...STEP_CITATION.source, evidence_version_id: null },
    };
    show("a", {
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        "GET /v1/citations": () =>
          json({ items: [unverified], total: 1 } satisfies ListPageCitationV2Out),
      },
    });
    const found = await card();
    expect(found.querySelector('[data-cite="unverified"]')?.textContent).toBe("Unverified");
    expect(found.textContent).not.toContain("recordkeeper");
  });

  it("the footer chips list the section's citations and its procedures", async () => {
    show("b");
    await card();
    const chips = Array.from(document.querySelectorAll<HTMLElement>('[data-cite="chip"]'));
    await waitFor(() => {
      expect(chips.map((c) => c.textContent)).toEqual(["Citations (3)", "Procedures (1)"]);
    });
  });
});

describe("hover intent, pin and Escape (DF-38, AC-9)", () => {
  async function bare(): Promise<HTMLElement> {
    restore = installFixtureMode(scenarios.a);
    renderRoutes([
      {
        path: "/",
        component: () => (
          <MatchScope>
            <table>
              <tbody>
                <tr>
                  <CitedCell
                    anchor={{ type: "workpaper", id: SERVICE_ORGS_WORKPAPER, ref: KEYSTONE_CELL }}
                  >
                    Keystone Retirement Services
                  </CitedCell>
                </tr>
              </tbody>
            </table>
            <CitationPopoverContainer />
          </MatchScope>
        ),
      },
    ]);
    return await screen.findByText("Keystone Retirement Services");
  }

  it("previews 150 ms after hover, closes 140 ms after leave, pins on click, Escape refocuses", async () => {
    const cell = await bare();
    await waitFor(() => {
      expect(cell.getAttribute("data-match")).toBeTruthy(); // the stack has loaded
    });
    vi.useFakeTimers();
    fireEvent.pointerEnter(cell);
    act(() => {
      vi.advanceTimersByTime(HOVER_INTENT_MS - 1);
    });
    expect(popover()).toBeNull();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(document.querySelector('[data-cite="card"]')?.className).toContain("opacity-95");
    fireEvent.pointerLeave(cell);
    act(() => {
      vi.advanceTimersByTime(140);
    });
    expect(document.querySelector('[data-cite="card"]')).toBeNull();
    vi.useRealTimers();
    fireEvent.click(cell);
    await waitFor(() => {
      expect(document.querySelector('[data-cite="card"]')?.hasAttribute("data-pinned")).toBe(true);
    });
    expect(cell.hasAttribute("data-lit")).toBe(true);
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
    await waitFor(() => {
      expect(document.querySelector('[data-cite="card"]')).toBeNull();
    });
    expect(document.activeElement).toBe(cell);
    expect(cell.hasAttribute("data-lit")).toBe(false);
  });
});
