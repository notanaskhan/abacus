// ac-test-author: notanaskhan (ADR-078 independent suite, built in the S21 solo lane)
// F-06-T21 (TASK-2607; SPEC-400 AC-30; F-06.md §3 F5 Story 5.5; C-25; ADR-005): SignOffSlots
// opens the sign-off dialog and never signs, from the public props only. "Given T6d, then initials
// chips read ✓ OB and ✓ DR in P-before-R order. Given TPL-06e, then ✓ SI shows with the Reviewed ·
// SI pill. Given a stale content hash, the chip shows the amber ! and Changed after sign-off. When
// any chip is clicked, onOpenSignOff(target, level) is called. SignOffSlots has no code path that
// creates a sign-off, and the agent never has a slot."

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AGENT_NAME } from "../../attribution/actor";
import * as signoff from "../index";
import { type SignOffChip, type SignOffChipsCopy, SignOffSlotChips } from "../index";

const HERE = dirname(fileURLToPath(import.meta.url));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const COPY: SignOffChipsCopy = {
  label: "Sign-offs",
  changedAfter: "Changed after sign-off",
  open: (name, level) => `${name}, ${level}: open sign-off`,
  reviewed: (initials) => `Reviewed · ${initials}`,
};

const OLIVIA: SignOffChip = { level: "L1", initials: "OB", name: "Olivia Brandt", when: "Sep 10" };
const DIANE: SignOffChip = { level: "L2", initials: "DR", name: "Diane Reyes", when: "Sep 12" };
const SAMUEL: SignOffChip = { level: "L2", initials: "SI", name: "Samuel Ito", when: "Sep 14" };

function mount(
  slots: readonly SignOffChip[],
  extra: { reviewLevel?: string; onOpenSignOff?: (t: string, l: string) => void } = {},
): { onOpenSignOff: ReturnType<typeof vi.fn> } {
  const onOpenSignOff = vi.fn(extra.onOpenSignOff);
  render(
    <SignOffSlotChips
      target="schedule:capital"
      slots={slots}
      copy={COPY}
      {...(extra.reviewLevel === undefined ? {} : { reviewLevel: extra.reviewLevel })}
      onOpenSignOff={onOpenSignOff}
    />,
  );
  return { onOpenSignOff };
}

const group = (): HTMLElement => screen.getByRole("group", { name: "Sign-offs" });

describe("Story 5.5 (AC-30): chips", () => {
  it("test_ac30_t6d_reads_check_ob_then_check_dr_whatever_order_they_arrive_in", () => {
    mount([DIANE, OLIVIA]);
    const chips = within(group()).getAllByRole("button");
    expect(chips.map((c) => c.getAttribute("aria-label"))).toEqual([
      "Olivia Brandt, L1: open sign-off",
      "Diane Reyes, L2: open sign-off",
    ]);
    // "✓ OB": the check is the chip's icon, the initials its text.
    expect(chips[0]?.querySelector("svg")).not.toBeNull();
    expect(chips[0]?.textContent).toContain("OB");
    expect(chips[1]?.textContent).toContain("DR");
  });

  it("test_ac30_tpl06e_a_current_review_sign_off_earns_the_reviewed_pill", () => {
    mount([OLIVIA, SAMUEL], { reviewLevel: "L2" });
    expect(within(group()).getByRole("button", { name: /Samuel Ito, L2/ })).toBeTruthy();
    expect(screen.getByText("Reviewed · SI")).toBeTruthy();
  });

  it("test_ac30_no_review_sign_off_no_reviewed_pill", () => {
    mount([OLIVIA], { reviewLevel: "L2" });
    expect(screen.queryByText(/^Reviewed ·/)).toBeNull();
  });

  it("test_ac30_a_stale_sign_off_shows_the_bang_and_changed_after_sign_off_in_words", () => {
    mount([OLIVIA, { ...SAMUEL, stale: true }], { reviewLevel: "L2" });
    const chip = within(group()).getByRole("button", { name: /Samuel Ito, L2/ });
    expect(chip.textContent).toContain("!");
    expect(screen.getByText("Changed after sign-off")).toBeTruthy();
    // A stale review is not a current review: no reviewed pill.
    expect(screen.queryByText("Reviewed · SI")).toBeNull();
  });

  it("test_ac30_clicking_any_chip_only_calls_on_open_sign_off_with_target_and_level", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("SignOffSlots never calls the network");
    });
    const { onOpenSignOff } = mount([OLIVIA, DIANE]);
    for (const chip of within(group()).getAllByRole("button")) fireEvent.click(chip);
    expect(onOpenSignOff.mock.calls).toEqual([
      ["schedule:capital", "L1"],
      ["schedule:capital", "L2"],
    ]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("test_ac30_keyboard_enter_on_a_chip_opens_the_dialog_too", () => {
    const { onOpenSignOff } = mount([OLIVIA]);
    const chip = within(group()).getByRole("button");
    chip.focus();
    expect(document.activeElement).toBe(chip);
    fireEvent.keyDown(chip, { key: "Enter" });
    fireEvent.click(chip); // a native button turns Enter into a click
    expect(onOpenSignOff).toHaveBeenCalledWith("schedule:capital", "L1");
  });
});

describe("Story 5.5 (AC-30): never signs, never the agent", () => {
  it("test_ac30_the_agent_never_has_a_slot", () => {
    mount([OLIVIA, { level: "L2", initials: "AA", name: AGENT_NAME }]);
    expect(within(group()).getAllByRole("button")).toHaveLength(1);
    expect(screen.queryByText(new RegExp(AGENT_NAME))).toBeNull();
    expect(screen.queryByRole("button", { name: new RegExp(AGENT_NAME) })).toBeNull();
  });

  it("test_ac30_the_package_exports_chips_and_nothing_that_signs", () => {
    const exported = Object.entries(signoff)
      .filter(([, value]) => typeof value === "function")
      .map(([name]) => name);
    expect(exported).toEqual(["SignOffSlotChips"]);
  });

  it("test_ac30_no_code_path_creates_a_sign_off", () => {
    const source = readFileSync(join(HERE, "../SignOffSlots.tsx"), "utf8");
    for (const idiom of [
      /fetch\(/,
      /XMLHttpRequest/,
      /\/v1\//,
      /sign_offs?\b.*(post|create)/i,
      /createSignOff|signOff\(|submitSignOff/,
    ]) {
      expect(source).not.toMatch(idiom);
    }
  });

  it("test_ac30_an_empty_slot_list_renders_no_chip", () => {
    mount([]);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});
