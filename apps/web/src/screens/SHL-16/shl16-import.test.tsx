// SHL-16 import variant and the j06 coordination step (P-04-T47). The acceptance is staged: "j06
// coordination passes on staging with the import checkpoint pending until Samuel Ito approves it,
// ready for the Jul 27 shadow." In fixture mode: the CCH import is Checkpoint 7 by the import
// (author line "Imported from CCH Axcess 2025I:FeldJ:V3"), pending until a person approves it, and
// approving it moves the return's sync chip from "Import pending approval" to "Out of sync".
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { OPENS as TAX02_OPENS, j06Scenario } from "../../fixtures/scenarios/TAX-02";
import { newQueryClient } from "../../testing/support";
import { ReturnOverviewPage } from "../TAX-02";
import { CheckpointDrawer } from ".";
import { OPENS, type Shl16State, scenarios } from "./scenarios";

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

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function spy(handlers: Record<string, FixtureHandler>, calls: Call[]) {
  return Object.fromEntries(
    Object.entries(handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
}

function drawer(state: Shl16State): Call[] {
  const calls: Call[] = [];
  const scenario = scenarios[state];
  restore = installFixtureMode({ ...scenario, handlers: spy(scenario.handlers, calls) });
  const open = OPENS[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CheckpointDrawer
        target={{ type: open.type, id: open.id }}
        {...(open.seq === undefined ? {} : { initialSeq: open.seq })}
        open
        onOpenChange={() => undefined}
      />
    </QueryClientProvider>,
  );
  return calls;
}

const card = (seq: number): HTMLElement | null =>
  document.querySelector<HTMLElement>(`[data-checkpoint="${String(seq)}"]`);

describe("SHL-16 import variant (P-04-T47)", () => {
  it("ia: Checkpoint 7 by the CCH import, pending, with the engine's values and Approve", async () => {
    const calls = drawer("ia");
    await waitFor(() => {
      expect(card(7)).not.toBeNull();
    });
    const seven = card(7) as HTMLElement;
    expect(seven.textContent).toContain("Imported from CCH Axcess 2025I:FeldJ:V3");
    expect(seven.textContent).toContain("Proposed");
    expect(seven.textContent).not.toContain("Accrued Agent");
    expect(await screen.findByText("Form 1040-ES (2026) vouchers")).toBeTruthy();
    expect(screen.getByText("Refund direct deposit")).toBeTruthy();
    const approve = screen.getByRole("button", { name: /Approve checkpoint/u });
    expect(approve.getAttribute("data-human-verb")).toBe("Approve");
    fireEvent.click(approve);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/approve"))).toBe(true);
    });
    const body = calls.find((c) => c.path.endsWith("/approve"))?.body as { seen_hash: string };
    expect(body.seen_hash.startsWith("sha256:7777")).toBe(true);
  });

  it("ib: approved by Samuel Ito, current, with no Approve", async () => {
    drawer("ib");
    await waitFor(() => {
      expect(card(7)?.textContent).toContain("Current");
    });
    expect(screen.queryByRole("button", { name: /Approve checkpoint/u })).toBeNull();
  });

  it("ie: rejected with the reason, never current", async () => {
    drawer("ie");
    await waitFor(() => {
      expect(card(7)?.textContent).toContain("Rejected");
    });
    expect(screen.getByText(/reason: Wait for final K-1/u)).toBeTruthy();
    expect(card(7)?.textContent).not.toContain("Current");
  });
});

describe("j06 coordination (P-04-T47): the CCH import approved as a checkpoint", () => {
  it("the chip reads Import pending approval until Samuel approves, then Out of sync", async () => {
    const calls: Call[] = [];
    const scenario = j06Scenario();
    restore = installFixtureMode({ ...scenario, handlers: spy(scenario.handlers, calls) });
    const returnId = TAX02_OPENS.a;
    render(
      <QueryClientProvider client={newQueryClient()}>
        <ReturnOverviewPage returnId={returnId} />
        <CheckpointDrawer
          target={{ type: "tax_return", id: returnId }}
          initialSeq={7}
          open
          onOpenChange={() => undefined}
        />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Import pending approval")).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: /Approve checkpoint/u }));
    expect(await screen.findByText("Out of sync")).toBeTruthy();
    expect(screen.queryByText("Import pending approval")).toBeNull();
    // Nothing approved itself: the one approve came from the person's click.
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });
});
