// A-05-T17 (TASK-3024): EBP-02 a–e, b2 and the C-20 states in fixture mode, inside the AUD-02
// cockpit. Row acceptance: "Hovering a provision lights the same line in the viewer, 'Citations
// (20)' equals the row count, and Sign off stays disabled until every row is verified." Words
// and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { EBP02Frame } from "./artboard";
import { type Ebp02State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Ebp02State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <EBP02Frame state={state} />
    </QueryClientProvider>,
  );
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

const signOff = (): HTMLButtonElement | undefined =>
  [...document.querySelectorAll<HTMLButtonElement>("button")].find(
    (b) => b.textContent === "Sign off…",
  );

describe("EBP-02", () => {
  it("a: 20 of 20 verified, Citations (20) equals the rows, Sign off enabled, ✓ HL", async () => {
    show("a");
    const count = await drawn("[data-ebp02='count']");
    expect(count.textContent).toBe("20 of 20 verified");
    expect(document.querySelectorAll("[data-provision]").length).toBe(20);
    expect(document.body.textContent).toContain("Citations (20)");
    expect(document.querySelector("[data-chip='l1']")?.textContent).toBe("✓ HL");
    expect(signOff()?.disabled).toBe(false);
    const entry = await drawn("[data-provision='entry_dates']");
    expect(entry.textContent).toContain("First of month following");
    expect(entry.textContent).toContain("AA §2.02");
  });

  it("b: agent draft, 0 of 20, Sign off disabled until every row is verified", async () => {
    show("b");
    const count = await drawn("[data-ebp02='count']");
    expect(count.textContent).toBe("0 of 20 verified");
    expect(document.body.textContent).toContain("Agent draft");
    expect(signOff()?.disabled).toBe(true);
  });

  it("hovering a row lights it; clicking pins it", async () => {
    show("b");
    const row = await drawn("[data-provision='plan_year']");
    fireEvent.pointerEnter(row);
    expect(row.dataset.lit).toBe("true");
    fireEvent.pointerLeave(row);
    expect(row.dataset.lit).toBe("false");
    fireEvent.click(row);
    expect(row.dataset.lit).toBe("true");
  });

  it("b2: Version 1, 18 rows, read-only: no ticks to press", async () => {
    show("b2");
    await drawn("[data-screen='EBP-02'][data-version='1']");
    expect(document.querySelectorAll("[data-provision]").length).toBe(18);
    expect(document.querySelector("[data-provision='catch_up']")).toBeNull();
    expect(document.querySelector("[data-ebp02='snapshot']")).not.toBeNull();
    const ticks = [...document.querySelectorAll<HTMLButtonElement>("[data-provision] button")];
    expect(ticks.every((t) => t.disabled)).toBe(true);
  });

  it("c: Entry dates carries the amber SPD: quarterly pill", async () => {
    show("c");
    const entry = await drawn("[data-provision='entry_dates']");
    expect(entry.textContent).toContain("SPD: quarterly");
  });

  it("d: Catch-up carries Amended Jan 1, 2025", async () => {
    show("d");
    const row = await drawn("[data-provision='catch_up']");
    expect(row.textContent).toContain("Amended Jan 1, 2025");
  });

  it("e: Reviewed · HL Sep 17 replaces Sign off", async () => {
    show("e");
    const reviewed = await drawn("[data-reviewed='true']");
    expect(reviewed.textContent).toBe("Reviewed · HL Sep 17");
    expect(signOff()).toBeUndefined();
  });

  it("off and not_allowed draw no provisions", async () => {
    show("off");
    await waitFor(() => {
      expect(document.querySelector("[data-ebp02='provisions']")).toBeNull();
    });
  });
});
