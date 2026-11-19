// G-04-T19 (TASK-8704): SHL-05 a-f and d' render from their scenarios; the request card offers
// Decline and Review in Settings (never a grant), the granted card offers Revoke, the offline chip
// and email line show in b, and the status rows use the canonical words.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { COPY as C } from "./copy";
import { SupportPanel } from "./index";
import { OPENING, type Shl05State, scenarios } from "./scenarios";

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(state: Shl05State, onReview = vi.fn(), onOpenChange = vi.fn()): void {
  restore = installFixtureMode(scenarios[state]);
  const o = OPENING[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <SupportPanel
        open
        onOpenChange={onOpenChange}
        initialTab={o.tab}
        initialArticle={o.article ?? null}
        onReview={onReview}
      />
    </QueryClientProvider>,
  );
}

describe("SHL-05 Support panel", () => {
  it("a: Ines's thread, the request card with Decline and Review in Settings", async () => {
    const onReview = vi.fn();
    show("a", onReview);
    expect(await screen.findByText(/CCH Axcess is accepting exports/)).toBeTruthy();
    expect(screen.getAllByText(/Ines at Accrued Support/).length).toBeGreaterThan(0);
    expect(screen.getByText(C.card.awaiting)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Approve|Grant/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: C.card.review }));
    expect(onReview).toHaveBeenCalledOnce();
    expect(screen.getByText(/Online · replies in ~4 min/)).toBeTruthy();
  });

  it("b: offline chip, Leave a message and the email line", async () => {
    show("b");
    expect(await screen.findByText(/Offline · we reply by 8:00 AM CT/)).toBeTruthy();
    expect(screen.getByText(C.offlineNotice("grace.holloway@brightwaterhale.com"))).toBeTruthy();
    expect(screen.getByPlaceholderText(C.composer.offline)).toBeTruthy();
  });

  it("c: granted by Felix Andersen until 11:41 AM with Revoke", async () => {
    show("c");
    expect(await screen.findByText(C.card.granted("Felix Andersen", "11:41 AM"))).toBeTruthy();
    expect(screen.getByRole("button", { name: C.card.revoke })).toBeTruthy();
  });

  it("d and d': the four group bands, then the article inside the drawer", async () => {
    show("d");
    expect(await screen.findByText("Suggested for this page")).toBeTruthy();
    expect(screen.getByText("Sending Form 8879 for e-signature")).toBeTruthy();
    cleanup();
    restore?.();
    show("d2");
    expect(
      await screen.findByRole("heading", {
        name: "Exporting a return to CCH Axcess: statuses and retries",
      }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: C.help.back })).toBeTruthy();
  });

  it("e: seven rows, CCH Axcess Tax export at Needs attention, the region line", async () => {
    show("e");
    expect(await screen.findByText("CCH Axcess Tax export")).toBeTruthy();
    expect(screen.getAllByText("Operational")).toHaveLength(6);
    expect(screen.getByText("Needs attention")).toBeTruthy();
    expect(screen.getByText(C.status.region("US"))).toBeTruthy();
  });

  it("f: the empty chat's two suggestions", async () => {
    show("f");
    expect(await screen.findByText("Ask about a sync")).toBeTruthy();
    expect(screen.getByText("Report a problem with an agent run")).toBeTruthy();
  });

  it("Escape closes the drawer", async () => {
    const onOpenChange = vi.fn();
    show("a", vi.fn(), onOpenChange);
    await screen.findByText(/CCH Axcess is accepting exports/);
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
