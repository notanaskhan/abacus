import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SignOffSlotChips } from "./SignOffSlots";

// F-06-T20 (C-25 presentational; F-06 §5.2): "a SignOffSlots click only calls onOpenSignOff".
// Initials chips in P-before-R order, a stale slot in words and an icon, the reviewed pill, no
// create path and no slot for the agent.

afterEach(cleanup);

const COPY = {
  label: "Sign-offs",
  changedAfter: "Changed after sign-off",
  open: (name: string, level: string): string => `${name}, ${level}: open sign-off`,
  reviewed: (initials: string): string => `Reviewed · ${initials}`,
};

describe("SignOffSlotChips", () => {
  it("orders the preparer before the reviewer whatever order the slots arrive in", () => {
    render(
      <SignOffSlotChips
        target="wp"
        copy={COPY}
        slots={[
          { level: "L2", initials: "DR", name: "Daniel Reyes" },
          { level: "L1", initials: "OB", name: "Olivia Brandt" },
        ]}
        onOpenSignOff={() => undefined}
      />,
    );
    const chips = within(screen.getByRole("group", { name: "Sign-offs" })).getAllByRole("button");
    expect(chips.map((c) => c.getAttribute("data-sign-off-chip"))).toEqual(["OB", "DR"]);
    expect(chips.map((c) => c.textContent)).toEqual(["OB", "DR"]);
  });

  it("a click only hands off to SHL-12 with the target and the level", () => {
    const open = vi.fn();
    render(
      <SignOffSlotChips
        target="workpaper:capital"
        copy={COPY}
        slots={[{ level: "L1", initials: "OB", name: "Olivia Brandt" }]}
        onOpenSignOff={open}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Olivia Brandt, L1: open sign-off" }));
    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith("workpaper:capital", "L1");
    expect(screen.queryByRole("button", { name: /^Sign off/ })).toBeNull();
  });

  it("states a stale slot in words and with the ! mark, never colour alone", () => {
    render(
      <SignOffSlotChips
        target="wp"
        copy={COPY}
        slots={[{ level: "L2", initials: "DR", name: "Daniel Reyes", stale: true }]}
        onOpenSignOff={() => undefined}
      />,
    );
    const chip = screen.getByRole("button", { name: "Daniel Reyes, L2: open sign-off" });
    expect(chip.hasAttribute("data-stale")).toBe(true);
    expect(chip.textContent).toContain("!");
    expect(chip.textContent).toContain("Changed after sign-off");
    expect(chip.querySelector("[data-icon]")).not.toBeNull();
    expect(screen.queryByText("Reviewed · DR")).toBeNull();
  });

  it("adds the Reviewed pill after a current review sign-off", () => {
    render(
      <SignOffSlotChips
        target="wp"
        copy={COPY}
        slots={[{ level: "L2", initials: "SI", name: "Samuel Ito" }]}
        onOpenSignOff={() => undefined}
      />,
    );
    expect(screen.getByText("Reviewed · SI")).toBeTruthy();
  });

  it("draws nothing without a signature: there is no empty slot to sign from here", () => {
    const { container } = render(
      <SignOffSlotChips target="wp" copy={COPY} slots={[]} onOpenSignOff={() => undefined} />,
    );
    expect(container.innerHTML).toBe("");
  });
});
