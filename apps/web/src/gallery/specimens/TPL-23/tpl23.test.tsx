// F-08-T15 (TASK-8847; handoff TPL-23): "Tiles read 63% / 214 / 3.1 / 9.0 / 4,812, the Granite Peak
// filter shows 65 / 62 / 3 / 48%, and TPL-23e hides names and Draft follow-ups."
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Tpl23Artboard } from ".";

afterEach(cleanup);
const at = (st: string) => render(<Tpl23Artboard params={{ st } as never} />);

describe("TPL-23 Insights · Client responsiveness", () => {
  it("a: tiles read 63% / 214 / 3.1 / 9.0 / 4,812", () => {
    at("a");
    for (const v of ["63%", "214", "3.1", "9.0", "4,812"])
      expect(screen.getAllByText(v).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Draft follow-ups…" })).toBeTruthy();
  });

  it("c: the Granite Peak filter shows 65 / 62 completed / 3 / 48%", () => {
    at("c");
    expect(screen.getAllByText("48%").length).toBeGreaterThan(0);
    expect(screen.getByText("65")).toBeTruthy();
    expect(screen.getByText("62 completed · 95.4%")).toBeTruthy();
    expect(screen.getAllByText("Late")).toHaveLength(3);
    expect(document.querySelector('[data-scope="client"]')?.className).toContain("bg-amber-tint");
  });

  it("e: restricted hides names behind locks and hides Draft follow-ups", () => {
    at("e");
    expect(document.querySelectorAll("[data-low-row] [data-locked-name]")).toHaveLength(5);
    expect(screen.queryByRole("button", { name: "Draft follow-ups…" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Fenwick Family Foundation" })).toBeNull();
  });

  it("f: flag off is the designed state", () => {
    at("f");
    expect(screen.getByText("Insights is not turned on for this firm.")).toBeTruthy();
  });

  it("no peer copy anywhere (D6)", () => {
    const { container } = at("a");
    expect(container.textContent).not.toMatch(/similar firms|peer benchmark|industry average/iu);
  });
});
