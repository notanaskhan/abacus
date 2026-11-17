import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { GroupScoping } from ".";
import { COMPONENTS, COPY } from "./copy";
import { AUD34_SCENARIOS } from "./scenarios";

// A-09-T31 (AUD-34 a to f): each artboard renders; the manager view disables every radio under
// the banner; coverage never shows 83%; no component PM is at or above group PM (180,000) and
// Operating Co. has none.

afterEach(cleanup);

describe("AUD-34 group scoping", () => {
  it.each(AUD34_SCENARIOS)("renders artboard %s", (st) => {
    const { container } = render(<GroupScoping st={st} />);
    expect(container.querySelector("[data-screen='AUD-34']")?.getAttribute("data-scenario")).toBe(
      st,
    );
  });

  it("disables every radio with the banner in the manager view (b)", () => {
    render(<GroupScoping st="b" />);
    expect(screen.getByRole("status").textContent).toBe(COPY.managerBanner);
    for (const radio of screen.getAllByRole("radio")) {
      expect(
        radio.getAttribute("aria-disabled") ?? String((radio as HTMLButtonElement).disabled),
      ).toMatch(/true/u);
    }
    expect(screen.getByRole("button", { name: COPY.remind })).toBeTruthy();
    expect(screen.queryByRole("button", { name: COPY.decide })).toBeNull();
  });

  it("keeps Decide disabled until a rationale is written (a)", () => {
    render(<GroupScoping st="a" />);
    expect(screen.getByRole("button", { name: COPY.decide })).toHaveProperty("disabled", true);
  });

  it.each(AUD34_SCENARIOS.filter((s) => s !== "f"))("never shows 83% in %s", (st) => {
    const { container } = render(<GroupScoping st={st} />);
    expect(container.textContent).not.toContain("83%");
  });

  it("keeps every component PM below group PM and none for Operating Co.", () => {
    for (const c of COMPONENTS) {
      if (c.pm === "—") {
        expect(c.name).toBe("Harlow & Pike Operating Co.");
        continue;
      }
      expect(Number(c.pm.replaceAll(",", ""))).toBeLessThan(180_000);
    }
  });

  it("offers Draft component instructions only once decided (c)", () => {
    render(<GroupScoping st="c" />);
    expect(screen.getByRole("button", { name: COPY.draftInstructions })).toBeTruthy();
    expect(screen.getByText(COPY.decidedLine)).toBeTruthy();
  });
});
