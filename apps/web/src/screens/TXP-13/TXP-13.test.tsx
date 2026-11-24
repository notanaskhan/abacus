// T-06-T45 (TASK-8935; DEC-5937): TXP-13 d from the landing — the banner reads exactly "From
// FY2026 audit · Final TB · handed off Nov 9", the tally 2,350,000 · 750,000 · 121 of 128 ·
// (68,400), and the M-1 starting point flags the passed adjustment without booking it.
import { client } from "@abacus/api-client/client";
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { TXP13 } from "./index";
import { TXP13_RETURN, noHandoff, scenarios } from "./scenarios";

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

describe("TXP-13 d · 1120 from the audit", () => {
  it("TXP-13d: banner, tally and M-1 starting point from the landing", async () => {
    restore = installFixtureMode(scenarios.d);
    renderRoutes([{ path: "/", component: () => <TXP13 returnId={TXP13_RETURN} /> }]);
    const banner = await screen.findByRole("note", { name: "Hand-off provenance" });
    expect(banner.textContent).toContain("From FY2026 audit · Final TB · handed off Nov 9");
    expect(banner.textContent).toContain("Open audit TB →");
    expect(banner.textContent).toContain("Hand-off details →");
    const pane = await screen.findByRole("region", { name: "Schedule M-1 — starting point" });
    expect(pane.textContent).toContain("2,350,000");
    expect(pane.textContent).toContain("750,000");
    expect(pane.querySelector("[data-candidate='AJE-3']")?.textContent).toContain("(68,400)");
    expect(pane.textContent).toContain("From the audit SUM · confirm all-events test");
    expect(pane.textContent).toContain(
      "Taxable income is computed after the 7 mapping items are reviewed. Nothing here changes the audited statements.",
    );
    expect(document.body.textContent).toContain("121 of 128");
  });

  it("TXP-13 a return with no hand-off draws no banner", async () => {
    restore = installFixtureMode(noHandoff);
    renderRoutes([{ path: "/", component: () => <TXP13 returnId={TXP13_RETURN} /> }]);
    expect(await screen.findByText("This return has no hand-off from an audit.")).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByRole("note", { name: "Hand-off provenance" })).toBeNull();
    });
  });
});
