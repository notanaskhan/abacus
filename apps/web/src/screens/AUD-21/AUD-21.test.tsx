// A-07-T28 (AUD-21 in fixture mode): every artboard state's status and primary action, the DRAFT
// watermark, the toggle that adds or removes its numbered paragraph, and the tabs.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { aud21 } from "../../fixtures/seed/audit-completion";
import { RepLetter } from "./RepLetter";

afterEach(cleanup);

const PRIMARY: Record<string, string | null> = {
  a: "Request partner approval…",
  a2: "Send for signature…",
  b: null,
  c: "Request partner approval…",
  d: "Remind…",
  e: null,
  f: "Start re-date…",
};

describe("AUD-21 representation letter", () => {
  for (const [state, label] of Object.entries(PRIMARY)) {
    it(`state ${state}: the primary action`, () => {
      render(<RepLetter letter={aud21(state as never)} />);
      if (label === null) {
        expect(
          screen.queryByRole("button", {
            name: /Send for signature|Remind|Start re-date|Request partner/,
          }),
        ).toBeNull();
      } else {
        expect(
          screen.getByRole("button", { name: new RegExp(label.replace("…", "")) }),
        ).toBeTruthy();
      }
    });
  }

  it("a draft carries the DRAFT watermark; the signed letter none", () => {
    render(<RepLetter letter={aud21("a")} />);
    expect(document.querySelector("[data-watermark='draft']")).not.toBeNull();
    cleanup();
    render(<RepLetter letter={aud21("e")} />);
    expect(document.querySelector("[data-watermark='draft']")).toBeNull();
    expect(screen.getByText("Dated October 9, 2026 = report date ✓ · G7")).toBeTruthy();
  });

  it("toggling a specific representation removes its paragraph", () => {
    render(<RepLetter letter={aud21("a")} />);
    expect(document.querySelector("[data-plan-paragraph='loan_offsets']")).not.toBeNull();
    fireEvent.click(
      screen.getByRole("switch", { name: "Loan offsets presented as benefits paid" }),
    );
    expect(document.querySelector("[data-plan-paragraph='loan_offsets']")).toBeNull();
  });

  it("b: the agent is drafting, shown as skeleton paragraphs", () => {
    render(<RepLetter letter={aud21("b")} />);
    expect(document.querySelector("[data-drafting]")).not.toBeNull();
  });

  it("a sent letter is read-only", () => {
    render(<RepLetter letter={aud21("d")} />);
    const toggle = screen.getByRole("switch", { name: "Tax status" });
    expect(
      toggle.hasAttribute("disabled") || toggle.getAttribute("aria-disabled") === "true",
    ).toBe(true);
  });
});
