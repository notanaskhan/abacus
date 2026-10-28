// POR-16 live swap (A-02-T28): the page's wiring in the portal. The back chip goes Home (until
// POR-12), Export instead opens the trial-balance request's guided steps, a stale second factor
// signs in again, and the OAuth return carries QuickBooks Online's company id (DEC-709). The
// staging walk (Tess Moreno connects the fake ledger end to end) is the batch pass's.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { connectionsHandlers } from "../../fixtures/handlers/connections";
import { portalHandlers } from "../../fixtures/handlers/portal";
import { POR16_CLOCKS } from "../../fixtures/seed/connections";
import { withRealm } from "../../legacy/ConnectCallback";
import { renderRoutes } from "../../testing/support";
import { PortalConnections, isStepUp } from ".";
import { scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(props: { onBack: () => void; onExportInstead: () => void }): void {
  const clock = POR16_CLOCKS.a;
  restore = installFixtureMode({
    ...scenarios.a,
    handlers: { ...portalHandlers({ clock }), ...connectionsHandlers("a", { clock }) },
  });
  renderRoutes([{ path: "/", component: () => <PortalConnections {...props} /> }]);
}

describe("POR-16 live wiring", () => {
  it("the back chip goes Home and Export instead opens Documents", async () => {
    const onBack = vi.fn();
    const onExportInstead = vi.fn();
    show({ onBack, onExportInstead });
    const qbo = await screen.findByRole("listitem", { name: "QuickBooks Online" });
    fireEvent.click(within(qbo).getByRole("button", { name: "Export instead" }));
    expect(onExportInstead).toHaveBeenCalledTimes(1);
    // The pane's back chip, after the portal nav's own "Home".
    fireEvent.click(screen.getAllByRole("button", { name: "Home" }).at(-1) as HTMLElement);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("knows a stale second factor from any other refusal", () => {
    expect(isStepUp({ detail: "forbidden", facts: { reason: "mfa_required" } })).toBe(true);
    expect(isStepUp({ detail: "forbidden" })).toBe(false);
    expect(isStepUp(null)).toBe(false);
  });

  it("carries QuickBooks Online's company id inside the code (DEC-709)", () => {
    expect(withRealm("abc", "9341453052194873")).toBe("abc~9341453052194873");
    expect(withRealm("abc", null)).toBe("abc");
    expect(withRealm("", "9341")).toBe("");
  });
});
