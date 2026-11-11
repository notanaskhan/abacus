// A-07-T47 (TASK-6737): AUD-24 on the server's data. The gates and rows are the server's, the
// release control shows only with `report.release` and a bound host, and it fires only after the
// partner's attestation; a refusal reads in words; nothing is optimistic.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { aud24 } from "../../fixtures/seed/audit-completion";
import { IssuanceLive } from "./IssuanceLive";

afterEach(cleanup);

const button = (): HTMLButtonElement | null =>
  screen.queryByRole("button", { name: /Release report…|Releasing…/ });

describe("AUD-24 live", () => {
  it("draws the server's gates and also-required rows", () => {
    render(<IssuanceLive release={aud24("a")} onRelease={vi.fn()} />);
    expect(document.querySelectorAll("[data-gate]").length).toBe(3);
    expect(document.querySelectorAll("[data-gate][data-met='true']").length).toBe(3);
    expect(document.querySelector("[data-also='bring_down'] ")?.textContent).toContain("#4240");
  });

  it("releases only after the attestation, and only with a bound host", () => {
    const onRelease = vi.fn();
    render(<IssuanceLive release={aud24("a")} onRelease={onRelease} />);
    fireEvent.click(button() as HTMLButtonElement);
    const confirm = screen.getByRole("button", { name: "Release report" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: "I am the engagement partner and I authorize release of this report",
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Release report" }));
    expect(onRelease).toHaveBeenCalledTimes(1);
    cleanup();
    render(<IssuanceLive release={aud24("a")} />);
    expect(button()).toBeNull();
  });

  it("b: blocked by G7, the button disabled", () => {
    render(
      <IssuanceLive
        release={{ ...aud24("b"), allowed_actions: ["report.release"] }}
        onRelease={vi.fn()}
      />,
    );
    expect(screen.getByText("Blocked by G7")).toBeTruthy();
    expect(button()?.disabled).toBe(true);
  });

  it("e: a non-partner sees who can release, never the button", () => {
    render(<IssuanceLive release={aud24("e")} onRelease={vi.fn()} />);
    expect(button()).toBeNull();
    expect(screen.getByText("Only Margaret Okonkwo can release this report")).toBeTruthy();
  });

  it("while ReleaseWorkflow runs the control reads Releasing… and stays disabled", () => {
    render(<IssuanceLive release={aud24("a")} running onRelease={vi.fn()} />);
    expect(button()?.textContent).toBe("Releasing…");
    expect(button()?.disabled).toBe(true);
  });

  it("d: released, with the server's time and name, and the archive date", () => {
    render(<IssuanceLive release={aud24("d")} onRelease={vi.fn()} tz="America/Chicago" />);
    expect(document.querySelector("[data-released='true']")?.textContent).toContain(
      "Margaret Okonkwo",
    );
    expect(screen.getByText("Archive by 2026-12-08")).toBeTruthy();
    expect(button()).toBeNull();
  });

  it("a refusal reads in words", () => {
    render(
      <IssuanceLive
        release={aud24("a")}
        onRelease={vi.fn()}
        problem="Not every gate is met yet."
      />,
    );
    expect(screen.getByRole("alert").textContent).toBe("Not every gate is met yet.");
  });
});
