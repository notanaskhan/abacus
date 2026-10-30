// KNW-04 i · Draft v3 (K-02-T14; SPEC-500 AC-52 to AC-55): the owner's draft with its two changed
// limits struck and amber-tinted, the "2 changes from v2" count, the sticky Save bar with the
// Effective date, Discard draft and Publish v3…, the staff view that never shows Publish, and the
// stale save's "Changed by … Reload" row.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { KNW04 } from ".";
import { type Knw04State, OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Knw04State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <KNW04 initial={OPENS[state]} />
    </QueryClientProvider>,
  );
}

describe("KNW-04 i (Priya Raman, draft v3 of AJE thresholds)", () => {
  it("shows Draft v3 with the two changed limits struck beside the new ones", async () => {
    show("i");
    expect(await screen.findByText("Draft v3")).toBeTruthy();
    const table = await screen.findByRole("table", { name: /Account class/ });
    const changed = table.querySelectorAll("[data-changed]");
    expect(changed).toHaveLength(2);
    expect(changed[0]?.textContent).toBe("$15,000$17,500");
    expect(changed[1]?.textContent).toBe("$10,000$12,500");
    expect(screen.getByText("2 changes from v2")).toBeTruthy();
    expect(screen.getByText("BH AJE thresholds v3")).toBeTruthy();
  });

  it("carries the sticky Save bar: count, Effective date, Discard draft, Publish v3…", async () => {
    show("i");
    expect(
      await screen.findByText("Draft v3 · 2 changes from v2 · visible to partners only"),
    ).toBeTruthy();
    expect((screen.getByLabelText("Effective") as HTMLInputElement).value).toBe("2026-10-01");
    expect(screen.getByRole("button", { name: "Discard draft" })).toBeTruthy();
    const publish = screen.getByRole("button", { name: "Publish v3…" });
    expect(publish.hasAttribute("disabled")).toBe(true); // a change summary first
    expect(screen.getByRole("button", { name: "New version…" }).hasAttribute("disabled")).toBe(
      true,
    );
  });

  it("edits a limit in place and marks it changed", async () => {
    show("i");
    const cell = await screen.findByRole("button", { name: /Prepaid expenses/ });
    fireEvent.click(cell);
    const input = screen.getByLabelText(/Prepaid expenses/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "11000" } });
    act(() => {
      input.blur();
    });
    await waitFor(() => {
      expect(screen.getByText("3 changes from v2")).toBeTruthy();
    });
    expect(screen.getByRole("button", { name: "Save draft" })).toBeTruthy();
  });

  it("shows the Changed by … Reload row when another partner saved first", async () => {
    show("i_stale");
    const cell = await screen.findByRole("button", { name: /Depreciation/ });
    fireEvent.click(cell);
    const input = screen.getByLabelText(/Depreciation/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "9000" } });
    act(() => {
      input.blur();
    });
    fireEvent.click(await screen.findByRole("button", { name: "Save draft" }));
    expect(
      await screen.findByText("Changed by Priya Raman. Reload to see the latest draft."),
    ).toBeTruthy();
  });
});

describe("KNW-04 a with no draft (staff never see Publish)", () => {
  it("never shows the draft or Publish to Cole Hart", async () => {
    show("draft_hidden");
    await screen.findByText("Review checklists");
    expect(screen.queryByText(/Publish v/)).toBeNull();
    expect(screen.queryByText(/Draft v3/)).toBeNull();
  });
});
