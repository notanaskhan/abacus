// C-01-T12 (TASK-8012): the close shell in fixture mode. Row acceptance: "Every C-01 route renders
// in fixture mode with the close header geometry (record bar 42, tabs 50) passing Tier D, and
// planned links render disabled with their target named." Tier D runs in the parity suite; here
// the header, the Review count, the disabled Deliverables tab and the flag-off state.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { CLOSE_IDS } from "../../fixtures/seed/closes";
import { newQueryClient } from "../../testing/support";
import { CloseShell } from "./CloseShell";
import { type ShellState, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: ShellState): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CloseShell
        closeId={CLOSE_IDS.august}
        tab="overview"
        screen="CLS-02"
        onTab={() => undefined}
        onClose={() => undefined}
        onBack={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("CLS-02 close shell", () => {
  it("draws Copperleaf August's record bar and close tabs with Review 7", async () => {
    show("shell");
    const bar = await waitFor(() => {
      const found = document.querySelector<HTMLElement>("[data-variant='close']");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(bar.textContent).toContain("Copperleaf Coffee Roasters, Inc.");
    expect(bar.textContent).toContain("Close");
    expect(bar.textContent).toContain("2026-08");
    for (const tab of ["Overview", "Intake", "Accounts", "Review", "Deliverables"]) {
      expect(bar.textContent).toContain(tab);
    }
    expect(bar.textContent).toContain("7");
  });

  it("renders Deliverables (CLS-08, C-02's) disabled", async () => {
    show("shell");
    const tab = await waitFor(() => {
      const found = Array.from(document.querySelectorAll<HTMLElement>("[role='tab']")).find((t) =>
        t.textContent.includes("Deliverables"),
      );
      expect(found).toBeDefined();
      return found as HTMLElement;
    });
    expect(tab.getAttribute("aria-disabled") === "true" || tab.hasAttribute("disabled")).toBe(
      true,
    );
  });

  it("shows the flag-off state inside the frame when closes.engine is off", async () => {
    show("off");
    await waitFor(() => {
      expect(document.querySelector("[data-flag-off='closes.engine']")).not.toBeNull();
    });
  });
});
