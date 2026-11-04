// A-06-T22 (TASK-3274): AUD-16 a, b, b2, c, d, e, f in fixture mode. Row acceptance: "Every AUD-16
// artboard renders from its scenario with totals only from the server, '$' appears only in the AJE
// list, and nothing reads Within threshold on an audit entry." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { type Aud16State, VIEW_OF, scenarios } from "../../fixtures/scenarios/AUD-16";
import { newQueryClient } from "../../testing/support";
import { SendEntriesBody } from "./SendEntries";
import { MisstatementsWorkbook } from "./Workbook";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Aud16State, onSend = vi.fn()): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <MisstatementsWorkbook
        auditId={NORTHWIND_AUDIT}
        view={VIEW_OF[state]}
        onView={() => undefined}
        onSend={onSend}
        onDecision={() => undefined}
      />
    </QueryClientProvider>,
  );
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

function noDollarOutside(selector: string): void {
  const outside = [...document.querySelectorAll<HTMLElement>("[data-screen='AUD-16'] *")]
    .filter((el) => el.children.length === 0 && el.closest(selector) === null)
    .map((el) => el.textContent);
  expect(outside.join(" ")).not.toContain("$");
}

describe("AUD-16", () => {
  it("a: the SUM foots from the server: 35,300 · 13,050 · 22,250 · 34,150 · (11,900)", async () => {
    show("a");
    const tally = await drawn("[data-aud16='tally']");
    expect(tally.textContent).toContain("12,610");
    expect(tally.textContent).toContain("189,150");
    expect(tally.textContent).toContain("252,200");
    expect(tally.textContent).toContain("v2 · 1.5%");
    expect(tally.textContent).toContain("18.1%");
    expect(tally.textContent).toContain("Below PM");
    const total = await drawn("[data-aud16='total']");
    expect(total.textContent).toBe("Total uncorrected35,30013,05022,25034,150(11,900)");
    expect(document.querySelector("[data-sum-row='PAJE-2']")?.textContent).toContain("(1,150)");
    expect(document.querySelector("[data-sum-row='PY-1']")?.textContent).toContain("(11,900)");
    expect(document.querySelector("[data-type='projected']")?.textContent).toBe("Projected");
    const bar = await drawn("[data-aud16='threshold-bar'] [data-fill]");
    expect(bar.dataset.fill).toBe("13.5");
    expect(document.querySelector("[data-aud16='caption']")?.textContent).toBe(
      "Aggregate 34,150 (rollover, the larger view) = 18.1% of PM. Below CT items are logged, not accumulated (1 item, 4,210).",
    );
    expect(document.querySelectorAll("[data-factor]").length).toBe(6);
    expect(document.querySelector("[data-aud16='decision']")?.textContent).toContain(
      "Awaiting Margaret Okonkwo",
    );
    expect(document.querySelector("[data-aud16='sign-off']")?.textContent).toContain(
      "Prepared · HL Sep 28",
    );
    noDollarOutside("[data-entry-amount]");
    expect(document.body.textContent).not.toContain("Within threshold");
    expect(document.body.textContent).not.toMatch(/\b(Post|Book)\b/);
  });

  it("b: AJE-1 client approved; its lines; '$' only in the list; All entries sent", async () => {
    show("b");
    const row = await drawn("[data-entry='AJE-1']");
    expect(row.textContent).toContain("Client approved · Dana Kowalski · Sep 25");
    expect(row.querySelector("[data-entry-amount]")?.textContent).toBe("$48,600");
    fireEvent.click(row.querySelector("button") as HTMLButtonElement);
    const lines = await drawn("[data-entry='AJE-1'] table");
    expect(lines.textContent).toContain("1250");
    expect(lines.textContent).toContain("33,540");
    expect(lines.textContent).toContain("15,060");
    expect(document.body.textContent).toContain("All entries sent");
    noDollarOutside("[data-entry-amount]");
    expect(document.body.textContent).not.toContain("Within threshold");
  });

  it("b2: Review required, Send to client… opens O3 with AJE-1", async () => {
    const onSend = vi.fn();
    show("b2", onSend);
    const row = await drawn("[data-entry='AJE-1'][data-status='review_required']");
    expect(row.textContent).toContain("Review required");
    const send = [...document.querySelectorAll("button")].filter(
      (b) => b.textContent === "Send to client…",
    );
    expect(send.length).toBeGreaterThan(0);
    await waitFor(() => {
      expect((send.at(-1) as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(send.at(-1) as HTMLButtonElement);
    expect(onSend).toHaveBeenCalledWith([expect.any(String)]);
  });

  it("c: RJE-1 reclassifies 14,850", async () => {
    show("c");
    const row = await drawn("[data-entry='RJE-1']");
    expect(row.textContent).toContain("Client approved · Sep 25");
    expect(row.textContent).toContain("$14,850");
  });

  it("d: BCT-1 4,210 is logged, not accumulated", async () => {
    show("d");
    const row = await drawn("[data-below-ct='BCT-1']");
    expect(row.textContent).toContain("Rollover received Dec 31, 2025, recorded Jan 2, 2026");
    expect(row.textContent).toContain("4,210");
    expect(row.textContent).toContain("Logged, not accumulated");
    expect(row.textContent).not.toContain("$");
  });

  it("e: concluded by Margaret Okonkwo; the strip reads ✓ MO; no Request conclusion", async () => {
    show("e");
    const decision = await drawn("[data-aud16='decision'][data-state='concluded']");
    expect(decision.textContent).toContain(
      "Immaterial individually and in aggregate · Concluded by Margaret Okonkwo",
    );
    expect(document.querySelector("[data-partner-signed='true']")?.textContent).toContain("MO");
    expect(document.body.textContent).not.toContain("Request conclusion…");
  });

  it("f: approaching PM turns the fill and the AGGREGATE card amber", async () => {
    show("f");
    const card = await drawn("[data-tally='aggregate'][data-warn='true']");
    expect(card.className).toContain("bg-amber-tint");
    expect(card.textContent).toContain("Approaching PM");
    const fill = await drawn("[data-aud16='threshold-bar'] [data-fill]");
    expect(fill.className).toContain("bg-amber");
  });

  it("off: adjustments.entries off draws C-20", async () => {
    show("off");
    await waitFor(
      () => {
        expect(document.body.textContent).toContain("not turned on");
      },
      { timeout: 6000 },
    );
    expect(document.querySelector("[data-aud16='sum']")).toBeNull();
  });
});

describe("AUD-16 O3 · Send to client", () => {
  it("shows the template's client wording, sends, and Undo calls only the undo command", async () => {
    const calls: string[] = [];
    const base = scenarios.b2;
    restore = installFixtureMode({
      ...base,
      get handlers() {
        const handlers = base.handlers;
        return Object.fromEntries(
          Object.entries(handlers).map(([key, handler]) => [
            key,
            key.startsWith("GET ")
              ? handler
              : (request: Parameters<typeof handler>[0]) => {
                  calls.push(key);
                  return handler(request);
                },
          ]),
        );
      },
    });
    {
      render(
        <QueryClientProvider client={newQueryClient()}>
          <SendEntriesBody
            workItemId={NORTHWIND_AUDIT}
            entryIds={["x"]}
            onDone={() => undefined}
          />
        </QueryClientProvider>,
      );
      const wording = await drawn("[data-client-wording]");
      expect(wording.textContent).toContain("December 26, 2025 payroll");
      fireEvent.click(
        [...document.querySelectorAll("button")].find(
          (b) => b.textContent === "Send",
        ) as HTMLElement,
      );
      const sent = await drawn("[data-aud16='sent']");
      fireEvent.click(
        [...sent.querySelectorAll("button")].find((b) => b.textContent === "Undo") as HTMLElement,
      );
      await waitFor(() => {
        expect(document.querySelector("[data-aud16='sent']")?.textContent).toContain(
          "Undone: nothing reached the client",
        );
      });
      expect(calls.filter((c) => c.includes("undo"))).toHaveLength(1);
      expect(calls.filter((c) => !c.includes("undo") && !c.includes("approve-and-send"))).toEqual(
        [],
      );
    }
  });
});
