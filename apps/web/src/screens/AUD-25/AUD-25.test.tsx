// A-07-T39 (AUD-25 in fixture mode): the six artboards, the clock's red tint only at 7 days or
// fewer, the lock as a person's act behind "Assembly is complete", the sealed state, additions
// after the lock and no delete control anywhere once locked.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Archive } from "./Archive";
import { FRAMES } from "./copy";

afterEach(cleanup);

describe("AUD-25 assembly and archive", () => {
  it.each(FRAMES)("%s renders its artboard from the fixture", (frame) => {
    render(<Archive frame={frame} canLock={frame !== "a" && frame !== "e"} />);
    expect(document.querySelector(`[data-screen='AUD-25'][data-frame='${frame}']`)).not.toBeNull();
    expect(screen.getByText("Binder index")).toBeTruthy();
  });

  it.each(["c", "d"] as const)("%s: no delete control exists once locked", (frame) => {
    render(<Archive frame={frame} canLock />);
    expect(screen.queryAllByRole("button", { name: /delete|remove/i })).toEqual([]);
    expect(document.querySelector("[data-readonly='true']")).not.toBeNull();
  });

  it("a: 8 of 9 with the open governance item, Request lock… and roll-forward disabled", () => {
    render(<Archive frame="a" />);
    expect(screen.getByText("8 of 9")).toBeTruthy();
    expect(screen.getByText("47 days")).toBeTruthy();
    expect(screen.getByText("13 of 60 days elapsed")).toBeTruthy();
    const request = screen.getByRole("button", { name: /Request lock…/ });
    expect((request as HTMLButtonElement).disabled).toBe(true);
    const roll = screen.getByRole("button", { name: /Archive and roll forward…/ });
    expect((roll as HTMLButtonElement).disabled).toBe(true);
    expect(roll.getAttribute("title")).toBe("Available once the archive can be locked (8 of 9)");
    expect(document.querySelector("[data-clock='archive'][data-risk='false']")).not.toBeNull();
  });

  it("b2: locking needs Assembly is complete and offers the roll-forward row", () => {
    const onLock = vi.fn();
    render(<Archive frame="b2" canLock onLock={onLock} />);
    expect(screen.getByRole("dialog", { name: "Lock the archive" })).toBeTruthy();
    expect(
      screen.getByText("Contents become read-only and are sealed with a SHA-256 hash"),
    ).toBeTruthy();
    const confirm = screen.getByRole("button", { name: "Lock archive" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Assembly is complete"));
    fireEvent.click(screen.getByLabelText("Then roll forward to PY2026 (ENG-13)"));
    fireEvent.click(confirm);
    expect(onLock).toHaveBeenCalledWith(true);
  });

  it("b: 9 of 9 and Lock archive… for a manager or the partner", () => {
    render(<Archive frame="b" canLock />);
    expect(screen.getByText("9 of 9")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Lock archive…/ })).toBeTruthy();
  });

  it("c: locked with the seal and G9, roll forward offered, the dock names what carries", () => {
    const onRollForward = vi.fn();
    render(<Archive frame="c" canLock onRollForward={onRollForward} />);
    expect(screen.getByText("Locked · sealed")).toBeTruthy();
    expect(
      screen.getByText("Locked Dec 3, 2026 · 4:18 PM · Hannah Leclerc · seal 7c41…a9e2 · G9 ✓"),
    ).toBeTruthy();
    expect(screen.getByText(/beginning balances 16,861,000/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Roll forward…/ }));
    expect(onRollForward).toHaveBeenCalledTimes(1);
  });

  it("d: the PI-02 addition is logged and more need a reason and the partner", () => {
    render(<Archive frame="d" canLock />);
    expect(screen.getByText("Addition logged")).toBeTruthy();
    expect(screen.getByRole("button", { name: /\+ Add after lock…/ })).toBeTruthy();
  });

  it("e: red tint only at 7 days or fewer", () => {
    render(<Archive frame="e" />);
    expect(screen.getByText("Archive in 5 days")).toBeTruthy();
    expect(document.querySelector("[data-clock='archive'][data-risk='true']")).not.toBeNull();
  });
});
