import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Tpl16Specimen } from ".";

// F-06-T04 (SPEC-400 AC-1, AC-2, AC-3): TPL-16b reads "1 of 2 signed" with only Mira's fields
// actionable, and TPL-16d lists all six evidence items, from envelope E6 in the tax seed.

afterEach(cleanup);

describe("TPL-16b: Mira signs E6", () => {
  it("AC-1: 1 of 2 signed, Dev's chips signed Sep 9 and Mira's open on both forms", () => {
    render(<Tpl16Specimen state="b" />);
    expect(document.querySelector("[data-envelope-pill]")?.textContent).toBe("1 of 2 signed");
    const chips = [...document.querySelectorAll("[data-signer-chips]")].map((c) => c.textContent);
    expect(chips).toEqual(["✓ Dev · Sep 9○ Mira", "✓ Dev · Sep 9○ Mira"]);
  });

  it("AC-1: the authorizing card states $2,296 and $410", () => {
    render(<Tpl16Specimen state="b" />);
    expect(
      screen.getByText(/Your federal refund is \$2,296 and your New York refund is \$410\./),
    ).toBeTruthy();
  });

  it("AC-2: only Mira's fields are controls; Dev's read as signed", () => {
    render(<Tpl16Specimen state="b" />);
    expect(screen.getAllByRole("button", { name: /^Sign here:/ })).toHaveLength(1);
    expect(screen.getByText("Dev Kapoor · signed electronically Sep 9, 2026")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\b\d{3}-\d{2}-\d{4}\b/);
  });
});

describe("TPL-16d: completed", () => {
  it("AC-3: all six evidence items, attributed to Mira, and the Completed pill", () => {
    render(<Tpl16Specimen state="d" />);
    const labels = [...document.querySelectorAll('[data-signing="evidence"] dt')].map(
      (d) => d.textContent,
    );
    expect(labels).toEqual(["Signed", "Method", "Identity", "IP address", "Login", "Documents"]);
    expect(screen.getByText("Signed. Thank you, Mira.")).toBeTruthy();
    expect(document.querySelector("[data-envelope-pill]")?.textContent).toContain("Completed");
    expect(document.body.textContent).not.toMatch(/Accrued/);
  });
});
