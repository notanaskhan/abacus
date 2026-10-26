// A-02-T09 (TASK-1286): AUD-06 in the AUD-02 cockpit, fixture mode. Row acceptance: "AUD-06a and
// AUD-06c pass their Vitest scenarios, clicking KRS Target 2045 lights its trust-report row within
// 360 ms, and no code path sums a column in the browser." Every figure checked here is the
// handoff's (spec.md, AUD-06a and c), read from what the screen renders.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { HARBORLINE_CITATIONS, HOVERED_2045 } from "../../fixtures/seed/trust";
import { newQueryClient } from "../../testing/support";
import { AuditCockpitPage } from "../AUD-02";
import { AUDIT_ID, scenarios as aud02Scenarios } from "../AUD-02/scenarios";
import { AUD06Frame } from "./artboard";
import { type Aud06State, scenarios } from "./scenarios";
import artboardSource from "./artboard.tsx?raw";
import paneSource from "./TrialBalance.tsx?raw";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Aud06State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AUD06Frame state={state} />
    </QueryClientProvider>,
  );
}

const row = (code: string): HTMLElement => {
  const found = document.querySelector<HTMLElement>(`[data-account='${code}']`);
  if (found === null) throw new Error(`no row ${code}`);
  return found;
};
const cells = (el: HTMLElement): string[] =>
  Array.from(el.querySelectorAll("td")).map((td) => td.textContent);
const totalRow = (key: string): string[] => {
  const found = document.querySelector<HTMLElement>(`[data-total='${key}']`);
  if (found === null) throw new Error(`no total ${key}`);
  return cells(found);
};
const litRegions = (): HTMLElement[] =>
  Array.from(document.querySelectorAll<HTMLElement>('[data-match-kind="region"][data-lit]'));

async function tableDrawn(): Promise<void> {
  await waitFor(
    () => {
      expect(document.querySelector("[data-aud06='lines']")).not.toBeNull();
    },
    { timeout: 4000 },
  );
}

describe("AUD-06a in the AUD-02 cockpit (A-02-T09)", () => {
  it("opens the Trial Balance row's workpaper with Hannah Leclerc's figures, $ and cents on every amount", async () => {
    show("a");
    await tableDrawn();
    expect(screen.getByRole("heading", { name: "Trial Balance" })).toBeTruthy();
    expect(cells(row("1130")).slice(0, 3)).toEqual([
      "KRS Target 2045 FundHL",
      "$2,388,970.00HL",
      "$2,915,330.00HL",
    ]);
    expect(totalRow("mutual_funds").slice(0, 3)).toEqual([
      "Total mutual funds & CITs",
      "$12,683,000.00",
      "$14,895,000.00",
    ]);
    expect(totalRow("investments").slice(0, 3)).toEqual([
      "Total investments at fair value",
      "$13,940,000.00",
      "$16,500,000.00",
    ]);
    expect(totalRow("net_assets").slice(0, 3)).toEqual([
      "Net assets available for benefits",
      "$14,228,500.00",
      "$16,812,400.00",
    ]);
    expect(within(row("1200")).queryByText("HL")).toBeNull(); // not reviewed: no chip
  });

  it("the check strip reads three tie pills and the loan rollforward's arithmetic in its tooltip", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-aud06='checks'] [data-status='tie']")).toHaveLength(
        3,
      );
    });
    const strip = screen.getByRole("group", { name: "Checks" });
    expect(strip.textContent).toBe(
      "Net assets ↔ trust reporttieBOY ↔ PY2024 audited FStieLoan rollforwardtie",
    );
    const loans = strip.querySelector<HTMLElement>("[data-check='loan-rollforward']");
    act(() => {
      loans?.focus();
    });
    const tip = await screen.findByRole("tooltip");
    expect(tip.textContent).toContain(
      "288,500.00 + 96,200.00 − 57,450.00 − 14,850.00 = 312,400.00",
    );
  });

  it("a ✓ HL chip says who signed what; the caption names who adopted it from where", async () => {
    show("a");
    await tableDrawn();
    const chip = within(row("1130")).getAllByRole("button", { name: /^Signed off by/ })[0];
    expect(chip?.getAttribute("aria-label")).toBe(
      "Signed off by Hannah Leclerc · Reviewer (L2) · Sep 14 2:05 PM",
    );
    expect(document.querySelector("[data-aud06='caption']")?.textContent).toBe(
      "Unadjusted. Imported by Marcus Delaney from the Accrued trial balance template, Sep 14, 10:02 AM.",
    );
  });

  it("AJE, RJE and Final are disabled with the A-06 tooltip while no adjustment source is registered", async () => {
    show("a");
    await tableDrawn();
    const layers = screen.getByRole("tablist", { name: "Layer" });
    const state = Object.fromEntries(
      within(layers)
        .getAllByRole("tab")
        .map((t) => [t.textContent, (t as HTMLButtonElement).disabled]),
    );
    expect(state).toEqual({ Unadjusted: false, AJE: true, RJE: true, Final: true });
    const wrapper = document.querySelector<HTMLElement>("[data-aud06='layers']");
    act(() => {
      wrapper?.focus();
    });
    expect((await screen.findByRole("tooltip")).textContent).toContain(
      "Adjustments arrive with Findings & adjustments",
    );
  });

  it("KRS Target 2045 lights its trust-report row in the Viewer dock, with the 360 ms match light", async () => {
    show("a");
    await tableDrawn();
    // The artboard opens on KRS Target 2045 (spec: SELECTED row, its Harborline row lit).
    await waitFor(
      () => {
        expect(litRegions()[0]?.getAttribute("data-match")).toBe(HOVERED_2045.match_id);
      },
      { timeout: 4000 },
    );
    fireEvent.click(screen.getByRole("button", { name: "KRS 500 Index Fund" }));
    await waitFor(() => {
      expect(litRegions()[0]?.getAttribute("data-match")).toBe(HARBORLINE_CITATIONS[0]?.match_id);
    });
    fireEvent.click(screen.getByRole("button", { name: "KRS Target 2045 Fund" }));
    await waitFor(() => {
      expect(litRegions()[0]?.getAttribute("data-match")).toBe(HOVERED_2045.match_id);
    });
    expect(row("1130").hasAttribute("data-selected")).toBe(true);
    expect(litRegions()[0]?.className).toContain("duration-[360ms]");
  });
});

describe("AUD-06c: does not tie (A-02-T09)", () => {
  it("the net-assets chip reads off 1,560.00 and BrokerWindow's EOY is red ink, flagged to an issue", async () => {
    show("c");
    await waitFor(() => {
      expect(document.querySelector("[data-check='net-assets-trust']")?.textContent).toBe(
        "Net assets ↔ trust reportoff 1,560.00",
      );
    });
    expect(
      document.querySelector("[data-check='net-assets-trust']")?.getAttribute("data-status"),
    ).toBe("off");
    const broker = row("1200");
    const flagged = broker.querySelector("[data-flagged]");
    expect(flagged?.textContent).toBe("$1,606,560.00");
    expect(broker.querySelectorAll("[data-flagged]")).toHaveLength(1);
    const flag = within(broker).getByRole("img", { name: "Does not tie · linked to an issue" });
    expect(flag.getAttribute("data-issue")).not.toBeNull();
    expect(totalRow("investments")[2]).toBe("$16,501,560.00");
  });
});

describe("the cockpit keeps AUD-06 behind ledger.tb_workpaper (DEC-314)", () => {
  it("with the flag off, the Trial Balance row draws no C9 workpaper", async () => {
    restore = installFixtureMode(aud02Scenarios.a);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <AuditCockpitPage auditId={AUDIT_ID} initial={{ section: "trial_balance" }} />
      </QueryClientProvider>,
    );
    await screen.findByRole("heading", { name: "Source Documents" });
    expect(document.querySelector("[data-aud06='lines']")).toBeNull();
    expect(screen.queryByRole("tablist", { name: "Layer" })).toBeNull();
  });
});

describe("no code path sums a column in the browser (ADR-050)", () => {
  it("the AUD-06 pane and artboard only format the server's figures", () => {
    for (const source of [paneSource, artboardSource]) {
      expect(source).not.toMatch(/\.reduce\(|\bsum\(|\bcents\(|BigInt\(|parseFloat\(|Number\(/u);
      expect(source).not.toMatch(/\.(?:eoy|boy|aje|rje|final|debit|credit|cy|py)\s*[-+]/u);
    }
  });
});
