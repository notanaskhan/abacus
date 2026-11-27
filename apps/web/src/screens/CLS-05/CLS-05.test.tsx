// C-01-T38 (TASK-8534): CLS-05 Reconciliation in fixture mode. Row acceptance: "Hover and keyboard
// focus light the matching statement line and back, the drawer's Propose is the only path to a
// proposed entry, and Reconciled shows only after the L1 sign-off."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { CLOSE_IDS } from "../../fixtures/seed/closes";
import { newQueryClient } from "../../testing/support";
import { CLS05, type CLS05Props } from "./index";
import { type Cls05State, INITIAL, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Cls05State, props: Partial<CLS05Props> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLS05 closeId={CLOSE_IDS.august} accountRef="35" initial={INITIAL[state]} {...props} />
    </QueryClientProvider>,
  );
}

async function sheet(): Promise<void> {
  await waitFor(() => {
    expect(document.querySelector("[data-cls05='tallies']")).not.toBeNull();
  });
}

const refundRow = (): HTMLElement =>
  document.querySelector<HTMLElement>("[data-cls05='book-side'] [data-match]") as HTMLElement;

describe("CLS-05 Reconciliation", () => {
  it.each(Object.keys(scenarios) as Cls05State[])("renders %s", async (st) => {
    show(st);
    await waitFor(() => {
      expect(document.querySelector("[data-screen='CLS-05']")).not.toBeNull();
    });
  });

  it("hover lights the matching statement line, and the statement line lights the rec line", async () => {
    show("a");
    await sheet();
    const row = refundRow();
    const match = row.getAttribute("data-match") ?? "";
    fireEvent.mouseEnter(row);
    await waitFor(() => {
      expect(
        document.querySelector(`[data-statement-line='${match}']`)?.hasAttribute("data-lit"),
      ).toBe(true);
    });
    fireEvent.mouseLeave(row);
    const stmt = document.querySelector<HTMLElement>(
      `[data-statement-line='${match}']`,
    ) as HTMLElement;
    fireEvent.mouseEnter(stmt);
    await waitFor(() => {
      expect(refundRow().hasAttribute("data-lit")).toBe(true);
    });
  });

  it("keyboard focus lights the pair the same way", async () => {
    show("a");
    await sheet();
    const row = refundRow();
    fireEvent.focus(row);
    const match = row.getAttribute("data-match") ?? "";
    await waitFor(() => {
      expect(
        document.querySelector(`[data-statement-line='${match}']`)?.hasAttribute("data-lit"),
      ).toBe(true);
    });
  });

  it("only the drawer's Propose proposes; the row button opens the drawer", async () => {
    const onPropose = vi.fn();
    show("a", { onPropose });
    await sheet();
    fireEvent.click(screen.getByRole("button", { name: "Propose AJE" }));
    expect(onPropose).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Propose" }));
    expect(onPropose).toHaveBeenCalledOnce();
  });

  it("Reconciled shows only after the L1 sign-off (d), never before (a, b, c)", async () => {
    for (const st of ["a", "b", "c"] as const) {
      show(st);
      await sheet();
      expect(document.querySelector("[data-cls05='reconciled']")).toBeNull();
      cleanup();
      restore?.();
    }
    show("d");
    await waitFor(() => {
      expect(document.querySelector("[data-cls05='reconciled']")?.textContent).toBe(
        "Reconciled ✓",
      );
    });
    expect(document.body.textContent).toContain("AJE-06 recorded in QuickBooks · JE 48218");
    expect(document.body.textContent).not.toMatch(/posted/iu);
  });

  it("b is off 380.00 with the Aug 27 line unmatched; c shows AJE-06 proposed", async () => {
    show("b");
    await sheet();
    expect(document.querySelector("[data-cls05='tallies']")?.textContent).toContain("380.00");
    expect(document.querySelector("[data-cls05='viewer']")?.textContent).toContain("Unmatched");
    cleanup();
    restore?.();
    show("c");
    await sheet();
    expect(screen.getByRole("button", { name: "AJE-06 proposed · Review required" })).toBeTruthy();
  });

  it("a3 lists the sign-off blockers; g shows the requested statement", async () => {
    show("a3");
    await sheet();
    expect(document.querySelector("[data-cls05='blockers']")?.textContent).toContain(
      "2 reconciling items are still open",
    );
    cleanup();
    restore?.();
    show("g");
    await waitFor(() => {
      expect(document.querySelector("[data-cls05='requested']")?.textContent).toBe(
        "Statement requested Sep 1, 2026",
      );
    });
  });

  // --- C-02-T56 (TASK-9027; DEC-6032): posted wording for a non-attest W1 client --------------

  function showPosting(attest: boolean): void {
    const base = scenarios.d;
    restore = installFixtureMode({
      ...base,
      handlers: {
        ...base.handlers,
        "GET /v1/me/capabilities": async (request) => {
          const res = await base.handlers["GET /v1/me/capabilities"]?.(request);
          const body = (await res?.json()) as { flags: Record<string, unknown> };
          return json({ ...body, flags: { ...body.flags, "adjustments.posting": true } });
        },
        "GET /v1/closes/{close_id}": async (request) => {
          const res = await base.handlers["GET /v1/closes/{close_id}"]?.(request);
          const body = (await res?.json()) as Record<string, unknown>;
          return json({ ...body, attest });
        },
      },
    });
    render(
      <QueryClientProvider client={newQueryClient()}>
        <CLS05 closeId={CLOSE_IDS.august} accountRef="35" initial={INITIAL.d} />
      </QueryClientProvider>,
    );
  }

  it("CLS-05 d acceptance: a non-attest W1 client reads AJE-06 posted (QBO 48218), its record CLS-07", async () => {
    showPosting(false);
    const note = await screen.findByText("AJE-06 posted (QBO 48218)");
    expect(note.closest("a")?.getAttribute("href")).toBe(
      `/closes/${CLOSE_IDS.august}/adjustments/AJE-06`,
    );
  });

  it("CLS-05 d: an attest client keeps the recorded wording, with no posted link", async () => {
    showPosting(true);
    expect(await screen.findByText("AJE-06 recorded in QuickBooks · JE 48218")).toBeTruthy();
    expect(screen.queryByText("AJE-06 posted (QBO 48218)")).toBeNull();
  });
});
