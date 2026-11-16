import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIELDWORK_COPY, postedOn } from "../domain/fieldwork";
import type { FixtureParams } from "../gallery/fixture-mode";
import { screenById } from "../gallery/fixture-mode";
import { KIT_A08_STATES, KitA08Board } from "./kit-a08";

// A-08-T26 (TASK-8088; AUD-12, AUD-13, AUD-14, AUD-26): every fieldwork kit state renders in the
// gallery without console errors; a score never shows without its reasons; the criteria filter
// toggles; Expand testing needs a rationale and an approver; Send stays disabled for a
// client-only address; the value chip lights its viewer region.

afterEach(cleanup);

function wrap(node: ReactNode): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

function at(st: string): void {
  render(wrap(<KitA08Board params={{ st, static: true } as FixtureParams} />));
}

describe("KIT-A08 fieldwork kit", () => {
  it("registers in the gallery", () => {
    expect(screenById("KIT-A08")).toBeDefined();
  });

  it("renders every state without console errors", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    for (const st of KIT_A08_STATES) {
      at(st);
      expect(document.querySelector(`[data-kit="A-08"][data-state="${st}"]`)).not.toBeNull();
      cleanup();
    }
    expect(error).not.toHaveBeenCalled();
    error.mockRestore();
  });

  it("shows the population tie and the five criteria counts exactly", () => {
    at("je");
    const population = document.querySelector('[data-fieldwork="population"]');
    expect(population?.textContent).toContain("214 of 214 accounts");
    const counts = Array.from(document.querySelectorAll("[data-criterion] td:last-child")).map(
      (td) => td.textContent,
    );
    expect(counts).toEqual(["142", "38", "61", "17", "9"]);
    expect(screen.getByText("236")).toBeDefined();
  });

  it("never shows a score without its reason codes, and weekend dates carry their day", () => {
    at("je");
    const rows = Array.from(document.querySelectorAll("[data-entry]"));
    expect(rows).toHaveLength(10);
    for (const row of rows) expect(row.querySelector("[data-reasons]")?.textContent).not.toBe("");
    expect(postedOn("2026-06-28", "Jun 28, 2026")).toBe("Jun 28, 2026 (Sun)");
    expect(postedOn("2026-06-13", "Jun 13, 2026")).toBe("Jun 13, 2026 (Sat)");
    expect(postedOn("2026-06-30", "Jun 30, 2026")).toBe("Jun 30, 2026");
  });

  it("toggles the criteria filter from a row", () => {
    at("je");
    const weekend = document.querySelector(
      '[data-criterion="weekend_holiday"] button',
    ) as HTMLButtonElement;
    fireEvent.click(weekend);
    expect(weekend.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(weekend);
    expect(weekend.getAttribute("aria-pressed")).toBe("false");
  });

  it("requests an expansion only with a rationale and an approver", () => {
    at("expand");
    const sheet = document.querySelector('[data-fieldwork="expand"]') as HTMLElement;
    expect(within(sheet).getByText(FIELDWORK_COPY.expand.becomes(50))).toBeDefined();
    const request = screen.getByRole("button", { name: FIELDWORK_COPY.expand.request });
    expect((request as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(sheet).getByLabelText(FIELDWORK_COPY.expand.rationaleLabel), {
      target: { value: "Exception on JE-26-17950: extend to the next ten by score." },
    });
    expect((request as HTMLButtonElement).disabled).toBe(false);
  });

  it("waits on the approver while an expansion is pending", () => {
    at("awaiting");
    expect(screen.getByText("Selected entries · 40 + 10 pending approval (HL)")).toBeDefined();
    expect(screen.getByText("Waiting on Hannah Leclerc")).toBeDefined();
  });

  it("keeps Send disabled for a client-only address, with the red helper", () => {
    at("new-confirmation");
    const send = screen.getByRole("button", { name: FIELDWORK_COPY.confirmations.send });
    expect((send as HTMLButtonElement).disabled).toBe(true);
    expect(document.querySelector('[data-fieldwork="send-helper"]')?.textContent).toBe(
      FIELDWORK_COPY.confirmations.notVerified,
    );
    fireEvent.click(screen.getByLabelText(FIELDWORK_COPY.confirmations.sourceNames.website));
    expect((send as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows Accept reconciliation only when the server allows it", () => {
    at("confirmations");
    expect(
      screen.getByRole("button", { name: FIELDWORK_COPY.confirmations.accept }),
    ).toBeDefined();
    expect(document.querySelector('[data-unreconciled="0.00"]')).not.toBeNull();
  });

  it("lights the viewer region from the value chip", () => {
    at("je");
    const chip = screen.getByRole("button", { name: "$100,000.00" });
    fireEvent.click(chip);
    expect(chip.getAttribute("aria-pressed")).toBe("true");
  });

  it("draws no dollar sign in the analytics table", () => {
    at("analytics");
    for (const table of document.querySelectorAll('[data-fieldwork="analytics"] tbody')) {
      expect(table.textContent).not.toContain("$");
    }
  });

  it("renders the rail for each SSARS mode", () => {
    at("ssars");
    const modes = Array.from(document.querySelectorAll('[data-fieldwork="ssars-rail"]')).map((n) =>
      n.getAttribute("data-mode"),
    );
    expect(modes).toEqual(["review", "compilation", "preparation"]);
  });
});
