import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidencePill } from "./pill";

// N-04-T09: green-tint at 0.95 and above, amber below, the percent in text.
describe("ConfidencePill", () => {
  it.each([
    [0.99, "high", "99%"],
    [0.95, "high", "95%"],
    ["0.9499", "low", "94%"],
    [0.71, "low", "71%"],
  ] as const)("%s reads %s with %s", (value, tone, text) => {
    const { container } = render(<ConfidencePill value={value} />);
    const pill = container.querySelector("[data-confidence]");
    expect(pill?.getAttribute("data-confidence")).toBe(tone);
    expect(pill?.textContent).toBe(text);
  });

  it("puts the note after the percent", () => {
    const { container } = render(<ConfidencePill value={0.71} note="date partly obscured" />);
    expect(container.textContent).toBe("71% · date partly obscured");
  });
});
