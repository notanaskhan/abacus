// TAX-09 · Tax-engine sync (T-01-T15). One test per artboard (a, a2, b, c, d, d2, e) and the
// non-artboard "Not yet exported" on its fixture scenario (SPEC-501 AC-11; T-01 §3.6), plus the
// row's acceptance: the disabled export names BH-TAX-02 and Daniel Reyes, and no chip state
// uses a tinted fill. axe and parity run in the walk.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { FELD_RETURN_ID } from "../../fixtures/seed/tax-compliance";
import { newQueryClient } from "../../testing/support";
import { TAX09 } from ".";
import { type Tax09State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
  window.matchMedia = (query: string) => ({
    matches: query.includes("reduce"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

function show(state: Tax09State, importOpen = false): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <TAX09 returnId={FELD_RETURN_ID} defaultOpen defaultImportOpen={importOpen} />
    </QueryClientProvider>,
  );
}

const popover = (): Promise<HTMLElement> =>
  screen.findByRole("dialog", { name: "Tax-engine sync" });
const chip = (name: RegExp): Promise<HTMLElement> => screen.findByRole("button", { name });

describe("TAX-09 chip states", () => {
  it("a2 · Ready for export, with Export open", async () => {
    show("a2");
    await chip(/Ready for export/);
    const actions = within(await popover()).getByRole("region", { name: "Actions" });
    expect(
      within(actions).getByRole<HTMLButtonElement>("button", { name: /Export to tax engine/ })
        .disabled,
    ).toBe(false);
  });

  it("a · Export generates the file; marking it exported reads Synced and adds the history row", async () => {
    show("a");
    const pop = await popover();
    fireEvent.click(within(pop).getByRole("button", { name: /Export to tax engine/ }));
    const dialog = await screen.findByRole("dialog", { name: "Mark exported" });
    expect(within(dialog).getByText("Download")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Mark exported" }));
    await chip(/Synced/);
    const history = within(await popover()).getByRole("region", { name: "History" });
    await waitFor(() => {
      expect(within(history).getByText("Return exported to tax engine")).toBeTruthy();
    });
    expect(within(history).getByText(/2025I:FeldJ:V3 · Just now/)).toBeTruthy();
    expect(within(history).queryByText("Not yet exported to tax engine")).toBeNull();
  });

  it("b · Synced Sep 10; Export disabled naming Daniel Reyes and BH-TAX-02", async () => {
    show("b");
    await chip(/Synced Sep 10/);
    const actions = within(await popover()).getByRole("region", { name: "Actions" });
    const exportItem = within(actions).getByRole<HTMLButtonElement>("button", {
      name: /Export to tax engine/,
    });
    expect(exportItem.disabled).toBe(true);
    expect(exportItem.textContent).toContain(
      "Final approval required — Daniel Reyes (BH-TAX-02) · Ridgeline K-1 is a Draft K-1 · pre-release",
    );
  });

  it("c · Out of sync: 3 fields changed after the last import", async () => {
    show("c");
    await chip(/Out of sync/);
    const history = within(await popover()).getByRole("region", { name: "History" });
    expect(within(history).getByText("Accrued changed after the last import")).toBeTruthy();
    expect(
      within(history).getByText("3 fields (Form 1040 line 2a, IT-201 lines 20 and 33)"),
    ).toBeTruthy();
  });

  it("d · Diagnostics returned: 0 errors · 2 informational, listed as plain text", async () => {
    show("d");
    const pop = await popover();
    expect(within(pop).getByText(/0 errors · 2 informational/)).toBeTruthy();
    const diagnostics = within(pop).getByRole("region", { name: "Diagnostics" });
    expect(within(diagnostics).getAllByRole("listitem")).toHaveLength(2);
  });

  it("d2 · Export failed with the IP PIN diagnostic", async () => {
    show("d2");
    await chip(/Export failed/);
    const diagnostics = within(await popover()).getByRole("region", { name: "Diagnostics" });
    expect(
      within(diagnostics).getByText(
        "Federal e-file — Identity Protection PIN required for the primary taxpayer (Jonah Feld)",
      ),
    ).toBeTruthy();
  });

  it("not yet exported · the History row says so", async () => {
    show("not_yet_exported");
    await chip(/Not yet exported/);
    const history = within(await popover()).getByRole("region", { name: "History" });
    expect(within(history).getByText("Not yet exported to tax engine")).toBeTruthy();
    expect(within(history).getByText("No export activity yet")).toBeTruthy();
  });

  it("no chip state uses a tinted fill", async () => {
    for (const state of ["a2", "b", "c", "d2", "not_yet_exported"] as const) {
      show(state);
      const button = (await screen.findAllByRole("button")).find(
        (b) => b.getAttribute("aria-haspopup") === "dialog",
      );
      expect(button?.className).not.toMatch(/bg-(green|red|amber)-tint/);
      cleanup();
      restore?.();
      restore = undefined;
    }
  });
});

describe("TAX-09 e · import diff", () => {
  it("lists the five fields with their causes and approves the accepted ones", async () => {
    show("e", true);
    const sheet = await screen.findByRole("dialog", {
      name: "Import from tax engine · 2025I:FeldJ:V3",
    });
    expect(
      within(sheet).getByText(
        "5 fields differ between CCH Axcess and Accrued. 0 conflict with cited workpaper values.",
      ),
    ).toBeTruthy();
    expect(within(sheet).getByText("4 × 19,990")).toBeTruthy();
    expect(
      within(sheet).getByText(
        "Entered in CCH Axcess by Samuel Ito · 110% of 2025 tax 123,223 = 135,545 − withholding 55,585 = 79,960 ÷ 4",
      ),
    ).toBeTruthy();
    expect(within(sheet).getByText(/equals 46\.0% × 307,900/)).toBeTruthy();
    expect(within(sheet).getByText(/equals 31\.5% × 307,900/)).toBeTruthy();
    expect(within(sheet).getAllByRole("checkbox")).toHaveLength(5);
    fireEvent.click(within(sheet).getByRole("button", { name: "Approve import" }));
    expect(await screen.findByText("Import approved")).toBeTruthy();
  });
});
