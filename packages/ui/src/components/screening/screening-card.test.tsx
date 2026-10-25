import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { ScreeningCardSpecimen } from "../../specimens/screening";
import { installDomShims } from "../../test-dom";
import { SCREENING_LABELS, ScreeningCard } from "./ScreeningCard";

// C-34 ScreeningCard (P-06-T22): the anatomy (header with time and verdict, two checks, the
// flagged-file band with View · Return…, the footer, the provenance), the four states, and the
// rules: no confidence percentage anywhere, and no human-only verb on the card's own controls.

beforeAll(installDomShims);
afterEach(cleanup);

const Q = SCREENING_LABELS.questions;
const CHECKS = [
  {
    key: "right_document",
    question: Q.right_document,
    verdict: "flag" as const,
    answer: "first answer",
  },
  {
    key: "right_period",
    question: Q.right_period,
    verdict: "pass" as const,
    answer: "second answer",
  },
];

describe("C-34 ScreeningCard", () => {
  it("draws the header, the checks, the flagged band, the footer and the provenance", () => {
    const view = vi.fn();
    const ret = vi.fn();
    const close = vi.fn();
    render(
      <ScreeningCard
        verdict="flagged"
        time="Sep 26, 10:12 AM"
        request="Request · expected period"
        checks={CHECKS}
        flagged={[{ id: "1", name: "a.pdf", reason: "why", onView: view, onReturn: ret }]}
        primary={{ label: "Draft follow-up", onClick: vi.fn() }}
        secondary={{ label: "Rerun", icon: "rotate-ccw", onClick: vi.fn() }}
        feedback={<button type="button">thumbs</button>}
        provenance="Screened by Accrued Agent · screener@v3 · 2 s"
        onClose={close}
      />,
    );
    const card = screen.getByRole("region", { name: "Evidence screening" });
    expect(card.textContent).toContain("Sep 26, 10:12 AM");
    expect(card.querySelector("[data-verdict]")?.textContent).toBe("Flagged");
    expect(
      Array.from(card.querySelectorAll("[data-check]")).map((c) =>
        c.getAttribute("data-check-verdict"),
      ),
    ).toEqual(["flag", "pass"]);
    const band = within(card).getByRole("region", { name: "Flagged files" });
    expect(band.textContent).toContain("1");
    fireEvent.click(within(band).getByRole("button", { name: "View a.pdf" }));
    fireEvent.click(within(band).getByRole("button", { name: "Return… a.pdf" }));
    expect(view).toHaveBeenCalledOnce();
    expect(ret).toHaveBeenCalledOnce();
    fireEvent.click(within(card).getByRole("button", { name: "Close" }));
    expect(close).toHaveBeenCalledOnce();
    expect(card.querySelector("[data-provenance]")?.textContent).toBe(
      "Screened by Accrued Agent · screener@v3 · 2 s",
    );
  });

  it("running: the spinner line, skeleton answers, no flagged band and a disabled footer", () => {
    render(
      <ScreeningCard
        verdict="flagged"
        running="Screening 2 new files…"
        checks={CHECKS}
        flagged={[{ id: "1", name: "a.pdf", onView: vi.fn(), onReturn: vi.fn() }]}
        primary={{ label: "Draft follow-up", onClick: vi.fn() }}
        secondary={{ label: "Rerun", onClick: vi.fn() }}
      />,
    );
    const card = screen.getByRole("region", { name: "Evidence screening" });
    expect(card.getAttribute("aria-busy")).toBe("true");
    expect(card.textContent).toContain("Screening 2 new files…");
    expect(card.textContent).not.toContain("first answer");
    expect(card.querySelectorAll("[data-pulse]").length).toBe(2);
    expect(within(card).queryByRole("region", { name: "Flagged files" })).toBeNull();
    for (const name of ["Draft follow-up", "Rerun"]) {
      expect(within(card).getByRole("button", { name }).hasAttribute("disabled")).toBe(true);
    }
  });

  it("passed and not screened read their words, and not screened draws its one line", () => {
    const { rerender } = render(
      <ScreeningCard verdict="passed" checks={CHECKS} summary="40 of 40" />,
    );
    expect(document.querySelector("[data-verdict]")?.textContent).toBe("Passed");
    expect(document.querySelector("[data-screening-summary]")?.textContent).toBe("40 of 40");
    rerender(<ScreeningCard verdict="not_screened" checks={CHECKS} notScreened="Not run yet." />);
    expect(document.querySelector("[data-verdict]")?.textContent).toBe("Not screened");
    expect(document.querySelectorAll("[data-check]")).toHaveLength(0);
    expect(document.body.textContent).toContain("Not run yet.");
  });

  it("the specimen shows no confidence percentage and no human-only verb", () => {
    const { container } = render(<ScreeningCardSpecimen />);
    expect(container.querySelectorAll("[data-screening-card]")).toHaveLength(4);
    expect(container.textContent).not.toMatch(/\d\s*%/);
    const labels = Array.from(container.querySelectorAll("button")).map((b) => b.textContent);
    for (const label of labels) {
      expect(label).not.toMatch(/\b(Approve|Sign off|Release|Send|Post|Decide)\b/);
    }
  });
});
