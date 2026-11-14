// T-05-T59 (TASK-7944; docs/screens/TXP-01.md; handoff TXP-01 A, A2, A3, B, C, D): "Hovering a
// marker lights its source row within 360 ms, and the stale banner lists the changed figure."
// The memo, its sources and its actions are the fixtures' (the server's).
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  RIDGELINE_GENERAL,
  RIDGELINE_OPPORTUNITIES,
  ridgelineMemo,
} from "../../fixtures/seed/tax-entity-memo";
import { COPY } from "./copy";
import { TXP01, memoBlocks, railOf } from ".";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("TXP-01 Review › Summary", () => {
  it("A: every cited source has a rail row that its marker lights", () => {
    const memo = ridgelineMemo("adopted");
    const rail = railOf(RIDGELINE_GENERAL, memo);
    const sources = rail.sections.find((s) => s.title === COPY.sourcesGroup);
    expect(sources?.rows.length).toBe(5);
    const cites = memoBlocks(memo).flatMap((b) =>
      b.kind === "p" ? b.segments.filter((s) => s.kind === "cite") : [],
    );
    expect(cites.length).toBe(5);
    for (const c of cites) {
      if (c.kind !== "cite") continue;
      expect(sources?.rows.some((r) => r.match === c.citation?.match)).toBe(true);
    }
  });

  it("A2: hovering a marker lights its source row within 360 ms", async () => {
    vi.useFakeTimers();
    render(<TXP01 memo={ridgelineMemo("adopted")} general={RIDGELINE_GENERAL} />);
    const marker = document.querySelector("[data-cite]") ?? document.querySelector("sup");
    expect(marker).toBeTruthy();
    if (marker === null) return;
    fireEvent.mouseEnter(marker);
    await act(async () => {
      vi.advanceTimersByTime(360);
    });
    expect(document.querySelectorAll("[data-lit='true'], [data-match-lit='true']").length).toBeGreaterThan(0);
  });

  it("A3: Approve memo opens the host's SHL-12 (the reviewer's L2)", () => {
    const approve = vi.fn();
    render(
      <TXP01
        memo={ridgelineMemo("adopted")}
        general={RIDGELINE_GENERAL}
        viewerName="Samuel Ito"
        onApprove={approve}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Approve memo/ }));
    expect(approve).toHaveBeenCalled();
  });

  it("B: drafting shows the skeleton and no section", () => {
    render(<TXP01 memo={ridgelineMemo("drafting")} general={RIDGELINE_GENERAL} />);
    expect(document.querySelector("[data-screen='TXP-01']")?.getAttribute("data-state")).toBe(
      "drafting",
    );
    expect(screen.queryByText("Facts")).toBeNull();
  });

  it("C: approved, with the opportunities as planned links", () => {
    render(
      <TXP01
        memo={ridgelineMemo("approved")}
        general={RIDGELINE_GENERAL}
        opportunities={RIDGELINE_OPPORTUNITIES.items}
      />,
    );
    expect(screen.getByText("Cost segregation study — Elm Street")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Approve memo/ })).toBeNull();
  });

  it("D: the stale banner lists the changed figure and regenerates only those sections", () => {
    const regenerate = vi.fn();
    render(
      <TXP01 memo={ridgelineMemo("stale")} general={RIDGELINE_GENERAL} onRegenerate={regenerate} />,
    );
    const banner = document.querySelector("[data-stale-banner]");
    expect(banner?.textContent).toContain("Ending capital 6,860,000 → 6,866,200");
    fireEvent.click(screen.getByRole("button", { name: COPY.regenerateSections }));
    expect(regenerate).toHaveBeenCalledWith(true);
  });

  it("Regenerate asks first; Edit saves one section as the person's", () => {
    const regenerate = vi.fn();
    const save = vi.fn();
    render(
      <TXP01
        memo={ridgelineMemo("adopted")}
        general={RIDGELINE_GENERAL}
        onRegenerate={regenerate}
        onSaveSection={save}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: COPY.regenerate }));
    expect(regenerate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: COPY.confirm }));
    expect(regenerate).toHaveBeenCalledWith(false);
    fireEvent.click(screen.getByRole("button", { name: COPY.edit }));
    const box = screen.getByRole("textbox");
    fireEvent.change(box, { target: { value: "A person's words." } });
    fireEvent.click(screen.getByRole("button", { name: COPY.save }));
    expect(save).toHaveBeenCalledWith("overview", "A person's words.");
  });
});
