// A-07-T29 (AUD-22 in fixture mode): the five required communications and their clocks, the
// recipients and sources, the selected letter's paper, and Approve & send only for the partner.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Governance } from "./Governance";

afterEach(cleanup);

describe("AUD-22 governance communications", () => {
  it("a: five rows, the planning letter selected and awaiting EP approval, DRAFT paper", () => {
    render(<Governance frame="a" canApproveSend />);
    expect(document.querySelectorAll("[data-comm-row]")).toHaveLength(5);
    expect(
      document.querySelector("[data-comm-row='planning_260']")?.getAttribute("aria-current"),
    ).toBe("true");
    expect(screen.getAllByText("Awaiting EP approval").length).toBeGreaterThan(0);
    expect(document.querySelector("[data-watermark='draft']")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Approve & send…" })).toBeTruthy();
    expect(
      screen.getByText("Our planned audit of the plan's 2025 financial statements"),
    ).toBeTruthy();
  });

  it("Approve & send is the partner's: a viewer without the action sees none", () => {
    render(<Governance frame="a" />);
    expect(screen.queryByRole("button", { name: "Approve & send…" })).toBeNull();
  });

  it("b: the planning letter sent and acknowledged; the paper is locked without a watermark", () => {
    render(<Governance frame="b" canApproveSend />);
    expect(screen.getByText("Sent Sep 18")).toBeTruthy();
    expect(screen.getByText("Acknowledged Sep 21 · Benefits Committee")).toBeTruthy();
    expect(document.querySelector("[data-watermark='draft']")).toBeNull();
    expect(screen.getByLabelText("Locked")).toBeTruthy();
  });

  it("c: the AU-C 265 letter selected with its 60-day clock and the 703 findings", () => {
    render(<Governance frame="c" canApproveSend />);
    expect(screen.getByText("Due Dec 8, 2026 · 60 days after release")).toBeTruthy();
    expect(
      screen.getByText(
        "Internal control and reportable findings — Northwind Robotics 401(k) Plan, 2025",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Reportable findings (AU-C 703)")).toBeTruthy();
  });

  it("selecting a row shows its letter", () => {
    render(<Governance frame="c" canApproveSend />);
    fireEvent.click(document.querySelector("[data-comm-row='planning_260']") as Element);
    expect(
      screen.getByText("Our planned audit of the plan's 2025 financial statements"),
    ).toBeTruthy();
  });
});
