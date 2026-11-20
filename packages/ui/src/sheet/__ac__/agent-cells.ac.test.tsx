// F-08-T11 (TASK-8750; ADR-078; ADR-005; F-08 §3 A3): agent cells never turn ink without a human
// adopt. A suggested cell stays suggested while onAdopt is pending or after it rejects; "Edited by
// HL · was Properly included" survives an edit; no citation marker renders without typed
// locators, even when the value contains "[1]"; no approve, sign off, release, send, adopt or
// accept control renders on an agent-owned element. Status words are the kit-local draft
// SheetCellState until F-08-T04's generated codes land.
import { act, cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SheetGrid } from "../SheetGrid";
import type { Actor } from "../../attribution/actor";
import type { SheetCellState } from "../types";
import { COLE, cellOf, grid, surlRow } from "./fixtures";

afterEach(cleanup);

const DRAFT_WORDS: readonly SheetCellState[] = [
  "empty",
  "human",
  "suggested",
  "adopted",
  "edited",
];
const RUNNING = { running: true }; // a stable snapshot (useSyncExternalStore)
const HUMAN_ONLY = /\b(approve|sign off|release|send|adopt|accept)\b/i;

function hoverAgent(rowKey = "SURL-04"): HTMLElement {
  const value = cellOf(rowKey, "conclusion").querySelector<HTMLElement>("[data-filled]");
  if (value === null) throw new Error("no agent value");
  fireEvent.mouseEnter(value.parentElement as HTMLElement);
  return value;
}
const filled = (rowKey = "SURL-04"): string | null =>
  cellOf(rowKey, "conclusion").querySelector("[data-filled]")?.getAttribute("data-filled") ?? null;

describe("F-08-T11 agent cells", () => {
  it("test_ac1_status_words_are_the_kit_local_draft_words", () => {
    grid();
    expect(DRAFT_WORDS).toEqual(["empty", "human", "suggested", "adopted", "edited"]);
    for (const el of document.querySelectorAll("[data-filled]")) {
      expect(DRAFT_WORDS).toContain(el.getAttribute("data-filled"));
    }
  });

  it("test_ac2_suggested_stays_suggested_while_onAdopt_is_pending", async () => {
    let resolve: () => void = () => undefined;
    const onAdopt = vi.fn(
      () =>
        new Promise<void>((r) => {
          resolve = r;
        }),
    );
    grid({ onAdopt });
    hoverAgent();
    fireEvent.click(screen.getByRole("button", { name: "Adopt" }));
    expect(onAdopt).toHaveBeenCalledWith("SURL-04", "conclusion");
    await act(async () => {
      await Promise.resolve();
    });
    expect(filled()).toBe("suggested");
    await act(async () => {
      resolve();
      await Promise.resolve();
    });
    expect(filled()).toBe("adopted");
  });

  it("test_ac3_suggested_stays_suggested_after_onAdopt_rejects", async () => {
    grid({ onAdopt: () => Promise.reject(new Error("409")) });
    hoverAgent();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Adopt" }));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(filled()).toBe("suggested");
    expect(cellOf("SURL-04", "conclusion").querySelector("[data-filled]")?.className).toContain(
      "text-ink-2",
    );
  });

  it("test_ac4_no_adopt_no_ink_without_onAdopt_and_never_for_a_non_person", () => {
    for (const viewer of [{ kind: "agent" }, { kind: "system" }] as Actor[]) {
      const { unmount } = grid({ viewer, onAdopt: () => Promise.resolve() });
      hoverAgent();
      expect(screen.queryByRole("button", { name: "Adopt" })).toBeNull();
      expect(filled()).toBe("suggested");
      unmount();
    }
  });

  it("test_ac5_edited_by_hl_was_properly_included_survives_an_edit", () => {
    const edited = surlRow("SURL-04", false, {
      value: "Improperly excluded",
      state: "edited",
      by: { kind: "human", name: "HL" },
      was: "Properly included",
    });
    const { rerender, props } = grid({ rows: [edited] });
    hoverAgent();
    expect(screen.getByRole("tooltip").textContent).toContain(
      "Edited by HL · was Properly included",
    );
    // A later save of another column re-renders the row; the edit trail stays.
    const again = {
      ...edited,
      version: 4,
      cells: { ...edited.cells, amount: { value: "68,900", state: "human" as const } },
    };
    rerender(<SheetGrid {...props} rows={[again]} />);
    hoverAgent();
    expect(screen.getByRole("tooltip").textContent).toContain(
      "Edited by HL · was Properly included",
    );
    expect(filled()).toBe("edited");
  });

  it("test_ac6_no_citation_marker_without_typed_locators_even_with_brackets", () => {
    grid({
      rows: [surlRow("SURL-04", false, { value: "Per [1] and [2]", state: "suggested" })],
    });
    hoverAgent();
    const tip = screen.getByRole("tooltip");
    expect(tip.textContent).not.toMatch(/\d+ citations?/);
    expect(tip.querySelectorAll("[title]")).toHaveLength(0);
    expect(
      cellOf("SURL-04", "conclusion").querySelectorAll("sup, [data-cite-marker]"),
    ).toHaveLength(0);
  });

  it("test_ac7_no_human_only_verb_on_an_agent_owned_element", () => {
    grid({
      viewer: COLE,
      onAdopt: () => Promise.resolve(),
      rows: [surlRow("SURL-04", false, { value: "Running", state: "empty" })],
      run: { subscribe: () => () => undefined, getSnapshot: () => RUNNING },
    });
    // Agent-owned: the column header and its menu, and an agent cell no person has adopted.
    const header = screen.getByRole("columnheader", { name: /Conclusion/ });
    for (const b of within(header).queryAllByRole("button")) {
      expect(b.textContent).not.toMatch(HUMAN_ONLY);
      expect(b.getAttribute("aria-label") ?? "").not.toMatch(HUMAN_ONLY);
    }
    for (const el of document.querySelectorAll('[data-actor="agent"]')) {
      for (const b of el.querySelectorAll("button")) expect(b.textContent).not.toMatch(HUMAN_ONLY);
    }
    expect(document.body.textContent).toContain("Agent column running");
  });
});
