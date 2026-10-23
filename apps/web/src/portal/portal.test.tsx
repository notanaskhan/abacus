// P-08-T07: the portal entry's shell data and loaders. The toolbar shows Approvals only for entity
// scopes; the branding loader names the tab after the firm (never the product); a reminder link
// leaves the address bar; the signed-in frame draws the nav from `/v1/me` → `portal`.
import { client } from "@abacus/api-client/client";
import { PortalBrandProvider } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../app-core/fixture-mode";
import { brandOf, portalToolbarData } from "../domain/portal";
import { scenarios } from "../fixtures/scenarios/POR-02";
import {
  BRIGHTWATER_BRANDING,
  NEUTRAL_BRANDING,
  PORTAL_SHELLS,
} from "../fixtures/seed/portal-home";
import { takeLinkFromFragment } from "../routes/portal/index";
import { newQueryClient } from "../testing/support";
import { PortalShell } from "./PortalShell";
import { applyBranding } from "./PortalRoot";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const labels = (slug: string, scopeId: string | null = null): string[] =>
  portalToolbarData("x", PORTAL_SHELLS[slug], scopeId).nav.map((n) => n.label);

describe("PortalToolbarData from /v1/me → portal", () => {
  it("shows Approvals only for an entity scope", () => {
    expect(labels("claire-feld")).toEqual([
      "Home",
      "Documents",
      "Questions",
      "Sign",
      "Messages",
      "Deliverables",
    ]);
    expect(labels("tess-moreno")).toContain("Approvals");
    // Even if the server's nav carried it, a household scope never shows Approvals.
    const household = {
      ...PORTAL_SHELLS["claire-feld"],
      nav: PORTAL_SHELLS["tess-moreno"]?.nav ?? [],
    };
    expect(
      portalToolbarData("x", household as NonNullable<(typeof PORTAL_SHELLS)[string]>).nav.map(
        (n) => n.label,
      ),
    ).not.toContain("Approvals");
  });

  it("lists every scope of a role union for the EntitySwitcher (Meera Shah)", () => {
    const bar = portalToolbarData("Meera Shah", PORTAL_SHELLS["meera-shah"]);
    expect(bar.scopes.map((s) => s.label)).toEqual([
      "Meera Shah",
      "Ridgeline Property Partners, LP",
    ]);
    expect(bar.scope?.label).toBe("Meera Shah");
  });

  it("draws no bell", () => {
    for (const slug of Object.keys(PORTAL_SHELLS)) {
      expect(labels(slug).map((l) => l.toLowerCase())).not.toContain("notifications");
    }
  });
});

describe("the portal's signed-in frame", () => {
  function frame(state: "a" | "d"): void {
    restore = installFixtureMode(scenarios[state]);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <PortalBrandProvider brand={brandOf(BRIGHTWATER_BRANDING)}>
          <PortalShell area="Home" />
        </PortalBrandProvider>
      </QueryClientProvider>,
    );
  }

  it("Claire Feld's toolbar: the firm's name, her nav without Approvals, her household", async () => {
    frame("a");
    const bar = await screen.findByRole("banner");
    expect(within(bar).getByText("Brightwater Hale")).toBeTruthy();
    expect(within(bar).queryByText("Approvals")).toBeNull();
    expect(screen.getByText("Jonah & Claire Feld")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/accrued/i);
  });

  it("Tess Moreno's toolbar shows Approvals for Copperleaf", async () => {
    frame("d");
    const bar = await screen.findByRole("banner");
    expect(within(bar).getByText("Approvals")).toBeTruthy();
    expect(screen.getByText("Copperleaf Coffee Roasters, Inc.")).toBeTruthy();
  });
});

describe("the branding loader", () => {
  it("names the tab after the firm's portal, or 'Client portal' on an unknown host", () => {
    const doc = document.implementation.createHTMLDocument("x");
    applyBranding(BRIGHTWATER_BRANDING, doc);
    expect(doc.title).toBe("Brightwater Hale");
    applyBranding(NEUTRAL_BRANDING, doc);
    expect(doc.title).toBe("Client portal");
    expect(doc.title).not.toMatch(/accrued/i);
  });

  it("uses the firm's logo for the tab icon when it has one", () => {
    const doc = document.implementation.createHTMLDocument("x");
    applyBranding({ ...BRIGHTWATER_BRANDING, logo_url: "/v1/portal/branding/logo" }, doc);
    expect(doc.querySelector("link[rel='icon']")?.getAttribute("href")).toBe(
      "/v1/portal/branding/logo",
    );
  });
});

describe("a reminder link in the fragment", () => {
  it("moves to the page's memory and leaves the address bar", () => {
    window.history.replaceState(null, "", "/sign-in#link=fixture-reminder-link-feld-2026-08-20");
    expect(takeLinkFromFragment()).toBe("fixture-reminder-link-feld-2026-08-20");
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe("/sign-in");
    expect(takeLinkFromFragment()).toBeUndefined();
  });
});
