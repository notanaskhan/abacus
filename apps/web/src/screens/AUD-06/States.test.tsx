// A-02-T14 (TASK-1338): AUD-06's remaining states in fixture mode. Row acceptance: "Each state
// matches its scenario, the agent never shows initials, and Hand off to tax and the entity strip
// are absent from production builds." Figures and words are the handoff's (spec.md STATES,
// revision.md R2 g and h), read from what the screen renders.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { AUD06Frame } from "./artboard";
import { type Aud06State, scenarios } from "./scenarios";
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

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 4000 },
  );
const cells = (el: Element): string[] =>
  Array.from(el.querySelectorAll("td")).map((td) => td.textContent);

describe("AUD-06b: the agent's draft (A-02-T14)", () => {
  it("reads Draft · Accrued Agent and every mark is an outlined agent tick, never initials", async () => {
    show("b");
    await drawn("[data-aud06='lines']");
    expect((await drawn("[data-aud06='draft']")).textContent).toBe("Draft · Accrued Agent");
    const agent = document.querySelectorAll("[data-tick='agent']");
    expect(agent.length).toBe(12);
    for (const tick of agent) {
      expect(tick.textContent).toBe("");
      expect(tick.getAttribute("title")).toBe("Accrued Agent");
    }
    expect(document.querySelectorAll("[data-tick='chip'], [data-tick='check']")).toHaveLength(0);
  });

  it("a person's trial balance (a) carries no draft pill", async () => {
    show("a");
    await drawn("[data-aud06='lines']");
    expect(document.querySelector("[data-aud06='draft']")).toBeNull();
  });
});

describe("AUD-06d: the Final layer (A-02-T14)", () => {
  it("selects Final, adds the AJE column with AJE-1 and reads net assets 16,861,000.00", async () => {
    show("d");
    await drawn("[data-aud06='lines']");
    const layers = screen.getByRole("tablist", { name: "Layer" });
    expect(within(layers).getByRole("tab", { selected: true }).textContent).toBe("Final");
    expect(screen.getByRole("columnheader", { name: "AJE" })).toBeTruthy();
    const receivable = await drawn("[data-account='contributions_receivable']");
    expect(cells(receivable).join(" ")).toContain("$48,600.00");
    expect(receivable.querySelector("[data-ref='AJE-1']")?.textContent).toBe("AJE-1");
    expect(document.querySelector("[data-total='net_assets']")?.textContent).toContain(
      "$16,861,000.00",
    );
  });
});

describe("AUD-06e: leadsheets in statement grammar (A-02-T14)", () => {
  it("draws the Investments leadsheet PY · CY · Δ · Δ% without $", async () => {
    show("e");
    const sheet = await drawn("[data-aud06='leadsheet']");
    expect(sheet.getAttribute("aria-label")).toBe("Investments");
    const total = sheet.querySelector<HTMLElement>("[data-row='total']");
    expect(cells(total as HTMLElement)).toEqual([
      "Investments",
      "13,940,000",
      "16,500,000",
      "2,560,000",
      "18.4%",
    ]);
    expect(sheet.textContent).not.toContain("$");
    // One area on Northwind's lines: no picker to choose between.
    expect(document.querySelector("[data-aud06='areas']")).toBeNull();
  });
});

describe("AUD-06g: Interim whole dollars with the TB label chip (A-02-T14)", () => {
  it("reads TB: Interim · 8/31/2026, one Interim 8/31/2026 column in whole dollars, Balances to 0", async () => {
    show("g");
    await drawn("[data-aud06='lines']");
    expect(screen.getByRole("button", { name: /TB: Interim · 8\/31\/2026/u })).toBeTruthy();
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toContain("Interim 8/31/2026");
    expect(headers).not.toContain("Beginning of Year");
    expect(document.querySelector("[data-total='total_assets']")?.textContent).toContain(
      "29,400,000",
    );
    expect(document.querySelector("[data-aud06='lines']")?.textContent).not.toMatch(/\.\d{2}/u);
    const strip = await drawn("[data-aud06='checks']");
    expect(strip.textContent).toBe("Balances to 0tie");
  });

  it("draws the entity strip in a dev or gallery build, Manufacturing open, the rest planned", async () => {
    show("g");
    const strip = await drawn("[data-aud06='entities']");
    const tabs = within(strip).getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual([
      "Holdings",
      "Operating Co.",
      "Manufacturing",
      "Distribution",
      "Real Estate",
    ]);
    expect(within(strip).getByRole("tab", { selected: true }).textContent).toBe("Manufacturing");
    expect(strip.textContent).toContain("Consolidated TB →");
  });

  it("a single-entity engagement draws no entity strip", async () => {
    show("a");
    await drawn("[data-aud06='lines']");
    expect(document.querySelector("[data-aud06='entities']")).toBeNull();
  });
});

describe("AUD-06h: Hand off to tax… (A-02-T14)", () => {
  it("is a disabled planned control on Granite Peak's Final layer, with the release tooltip", async () => {
    show("h");
    await drawn("[data-aud06='lines']");
    const wrapper = await drawn("[data-aud06='hand-off']");
    const button = within(wrapper).getByRole("button", { name: "Hand off to tax…" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    act(() => {
      wrapper.focus();
    });
    expect((await screen.findByRole("tooltip")).textContent).toContain(
      "Final TB released Oct 27, 2026 → FY2026 Form 1120 · Granite Peak Outdoor Supply, Inc.",
    );
  });

  it("is never offered on Northwind (an EBP audit with no return)", async () => {
    show("d");
    await drawn("[data-aud06='lines']");
    expect(document.querySelector("[data-aud06='hand-off']")).toBeNull();
  });
});

describe("production builds draw neither Hand off to tax nor the entity strip", () => {
  it("both controls sit behind PLANNED_VISIBLE, which a production build folds to false", () => {
    expect(paneSource).toMatch(/PLANNED_VISIBLE && planned\.handOffToTax !== undefined/u);
    expect(paneSource).toMatch(/PLANNED_VISIBLE && \(planned\.entities\?\.length \?\? 0\) > 1/u);
    // Each appears once, so no unguarded copy draws either.
    expect(paneSource.match(/data-aud06="hand-off"/gu)).toHaveLength(1);
    expect(paneSource.match(/data-aud06="entities"/gu)).toHaveLength(1);
  });
});
