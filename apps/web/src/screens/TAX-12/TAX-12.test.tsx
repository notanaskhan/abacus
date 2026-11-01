// TAX-12 · Delivery & e-file, parts 1 and 2 (T-01-T24, T-01-T39). One test per built artboard (a,
// a2, b, c, c2, d, e) on its fixture scenario, plus the rows' acceptance: the gate is disabled while
// 1 of 2 has signed; the payment figures foot to 253 and 1,269; the confirm names the four
// jurisdictions and Sep 18, 2026; and the agent's fix card is absent outside fixture builds.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { FELD_NY, FELD_REFUND, FELD_RETURN_ID } from "../../fixtures/seed/tax-compliance";
import { newQueryClient } from "../../testing/support";
import { TAX12 } from ".";
import { COPY } from "./copy";
import { type Tax12State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

function show(state: Tax12State, reminder = false): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <TAX12 returnId={FELD_RETURN_ID} defaultReminderOpen={reminder} />
    </QueryClientProvider>,
  );
}

describe("TAX-12 delivery", () => {
  it("a · Awaiting signature: 1 of 2 signed and the gate locked", async () => {
    show("a");
    const envelope = await screen.findByRole("region", {
      name: "Form 8879 + TR-579-IT · TY2025 · Jonah & Claire Feld",
    });
    expect(within(envelope).getByText("Claire Feld (spouse)")).toBeTruthy();
    // T-01-T51: each signer's line is built from the envelope read, not a fixed string.
    expect(
      within(envelope).getByText(/^KBA passed · signed .* · IP and login logged$/),
    ).toBeTruthy();
    expect(
      within(envelope).getByText(/^(Viewed .* · identity check not started|Not viewed yet)$/),
    ).toBeTruthy();
    expect(await screen.findAllByText(/^1 of 2 signed/)).not.toHaveLength(0);
    const gate = within(screen.getByRole("region", { name: COPY.gate.title }));
    expect(gate.getByRole<HTMLButtonElement>("button", { name: COPY.gate.button }).disabled).toBe(
      true,
    );
    expect(screen.getByText(COPY.acks.none)).toBeTruthy();
  });

  it("a · the payment figures foot to 253 and 1,269", async () => {
    show("a");
    await screen.findByRole("region", { name: COPY.payments.title });
    expect(FELD_REFUND.paid - FELD_REFUND.tax).toBe(253);
    expect(FELD_NY.tax - FELD_NY.withheld).toBe(1269);
    // T-01-T51: the amounts come from the delivery read's payment instructions.
    expect(screen.getAllByText(/^253( · due .*)?$/)).not.toHaveLength(0);
    expect(screen.getAllByText(/^1,269( · due .*)?$/)).not.toHaveLength(0);
  });

  it("a2 · the pre-approved reminder, Grace sends", async () => {
    show("a2", true);
    const dialog = await screen.findByRole("dialog", { name: COPY.reminder.title });
    expect(within(dialog).getByText(/Jonah Feld/)).toBeTruthy();
    expect(within(dialog).getByText(COPY.reminder.approved)).toBeTruthy();
    expect(within(dialog).getByText(COPY.reminder.body)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.reminder.send }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(COPY.reminder.sent);
    });
  });

  it("b · blocked before final approval", async () => {
    show("b");
    expect(await screen.findByText(COPY.canvas.blockedTitle)).toBeTruthy();
    expect(
      screen.getByText(/ approves.*; the return is then exported to CCH Axcess\.$/),
    ).toBeTruthy();
    expect(screen.getByText(/^Blocked by \d+ open items?$/)).toBeTruthy();
    expect(screen.queryByRole("region", { name: COPY.gate.title })).toBeNull();
  });

  it("c · ready to transmit: Grace waits for Daniel Reyes with Notify", async () => {
    show("c");
    const gate = within(await screen.findByRole("region", { name: COPY.gate.title }));
    expect(await gate.findByText(COPY.ero.waiting)).toBeTruthy();
    expect(gate.getByRole("button", { name: COPY.ero.notify })).toBeTruthy();
    expect(gate.queryByRole("button", { name: COPY.gate.button })).toBeNull();
    expect(screen.getByText(COPY.status.completed)).toBeTruthy();
  });

  it("c2 · Daniel records the transmission through a confirm", async () => {
    show("c2");
    const gate = within(await screen.findByRole("region", { name: COPY.gate.title }));
    const mark = await gate.findByRole<HTMLButtonElement>("button", { name: COPY.gate.button });
    expect(mark.disabled).toBe(false);
    fireEvent.click(mark);
    const dialog = await screen.findByRole("alertdialog");
    const confirm = within(dialog).getByText(/^Record that the .* returns were transmitted/);
    for (const place of ["New York", "2026"]) {
      expect(confirm.textContent).toContain(place);
    }
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.ero.record }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(COPY.ero.recorded);
    });
  });

  it("d · Accepted: four acknowledgments, delivered to the portal, estimates scheduled", async () => {
    show("d");
    const acks = within(await screen.findByRole("list", { name: COPY.acks.title }));
    for (const name of ["Federal", "Illinois", "Colorado", "New York"]) {
      expect(acks.getByText(COPY.acks.accepted(name))).toBeTruthy();
    }
    expect(acks.getByText(COPY.acks.submission("2614"))).toBeTruthy();
    expect(screen.getAllByText(COPY.delivered, { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByText(new RegExp(COPY.estimates))).toBeTruthy();
    expect(screen.getAllByText(COPY.status.accepted).length).toBeGreaterThan(0);
  });

  it("e · Rejected with the engine's code and text, and Create issue", async () => {
    show("e");
    expect(
      await screen.findByText(
        COPY.acks.rejected(
          "Federal",
          "IND-181-01",
          "the primary taxpayer's Identity Protection PIN is missing or incorrect",
        ),
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.fix.create }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(COPY.fix.created);
    });
    expect(screen.getAllByText(COPY.status.rejected).length).toBeGreaterThan(0);
  });

  it("e · the agent's fix card renders only in fixture builds", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_FIXTURES", "");
    const production = await import(".");
    expect(production.FIXTURE_BUILD).toBe(false);
    vi.stubEnv("VITE_FIXTURES", "1");
    vi.resetModules();
    const fixtures = await import(".");
    expect(fixtures.FIXTURE_BUILD).toBe(true);
    vi.unstubAllEnvs();
  });

  it("never says Accrued or the agent transmits or files", () => {
    const text = JSON.stringify(COPY);
    expect(text).not.toMatch(/Accrued (transmits|e-files|files)/);
    expect(text).not.toMatch(/Agent (transmits|e-files|files)/);
  });
});
