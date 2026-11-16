import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Beneficiaries, TXT03_SCENARIOS, releaseEnabled } from ".";

// T-07-T25 (TXT-03 A to E): each state renders; Release is enabled only when both gate facts
// hold; after release each beneficiary's K-1 reads released.

afterEach(cleanup);

describe("TXT-03 beneficiaries", () => {
  it.each(TXT03_SCENARIOS)("renders state %s", (st) => {
    const { container } = render(<Beneficiaries st={st} />);
    expect(container.querySelector("[data-screen='TXT-03']")?.getAttribute("data-scenario")).toBe(
      st,
    );
  });

  it("enables Release only when both gate facts are true", () => {
    expect(releaseEnabled({ finalApproved: true, form8879fSigned: true })).toBe(true);
    expect(releaseEnabled({ finalApproved: true, form8879fSigned: false })).toBe(false);
    expect(releaseEnabled({ finalApproved: false, form8879fSigned: true })).toBe(false);
    render(<Beneficiaries st="a" />);
    expect(screen.getByRole("button", { name: "Release K-1s…" })).toHaveProperty("disabled", true);
  });

  it("releases each beneficiary's K-1 in the released state", () => {
    const { container } = render(<Beneficiaries st="b" />);
    const statuses = [...container.querySelectorAll("[data-k1-status]")].map((n) => n.textContent);
    expect(statuses).toEqual(["Released Sep 28", "Released Sep 28"]);
  });
});
