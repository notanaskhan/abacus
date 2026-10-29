import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Tpl19Frame9 } from ".";

// F-06-T06 (Story 1.6): TPL-19 frame 9 hands off to the same ceremony at 390 with its own 72 bar.

afterEach(cleanup);

describe("TPL-19 frame 9: mobile sign", () => {
  it("Form 8879 · TY2025 with the 1 of 2 signed pill and a 72 sticky bar", () => {
    render(<Tpl19Frame9 frame />);
    expect(document.querySelector('[data-layout="phone"] h1')?.textContent).toBe(
      "Form 8879 · TY2025 · Dev & Mira Kapoor",
    );
    expect(document.querySelector("[data-envelope-pill]")?.textContent).toBe("1 of 2 signed");
    expect(
      document.querySelector('[data-signing="mobile-sign-bar"]')?.getAttribute("data-height"),
    ).toBe("72");
  });
});
