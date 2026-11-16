import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ComponentAuditors } from ".";
import { COPY, DELIVERABLE_STATUSES } from "./copy";
import { AUD35_SCENARIOS } from "./scenarios";

// A-09-T22 (AUD-35 a to g): each artboard renders; Send instructions is disabled with its reason
// in a; no deliverable status outside Expected, Received, Reviewed and Late renders.

afterEach(cleanup);

describe("AUD-35 component auditors", () => {
  it.each(AUD35_SCENARIOS)("renders artboard %s", (st) => {
    const { container } = render(<ComponentAuditors st={st} />);
    expect(container.querySelector("[data-screen='AUD-35']")?.getAttribute("data-scenario")).toBe(
      st,
    );
  });

  it("disables Send instructions with its reason in a", () => {
    render(<ComponentAuditors st="a" />);
    const send = screen.getByRole("button", { name: COPY.send });
    expect(send).toHaveProperty("disabled", true);
    expect(send.getAttribute("title")).toBe(COPY.sendBlocked);
  });

  it.each(AUD35_SCENARIOS.filter((s) => s !== "g"))(
    "renders only the four deliverable statuses in %s",
    (st) => {
      const { container } = render(<ComponentAuditors st={st} />);
      const statuses = [...container.querySelectorAll("[data-deliverable-status]")].map((n) =>
        n.getAttribute("data-deliverable-status"),
      );
      expect(statuses.length).toBe(4);
      for (const s of statuses) expect(DELIVERABLE_STATUSES).toContain(s);
    },
  );
});
