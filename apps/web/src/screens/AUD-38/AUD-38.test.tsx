// T-06-T45 (TASK-8935; DEC-5937): AUD-38 a–e from the Python slice's previews. Acceptance: "Hand
// off is the only primary button, focus stays trapped in the sheet, and the banner copy matches
// the revision exactly" (the TXP-13 banner: "From FY2026 audit · Final TB · handed off Nov 9").
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { AUD38_AUDIT_ID, type Aud38State, preview, scenarios } from "./scenarios";
import { renderRoutes } from "../../testing/support";
import { toast } from "@abacus/ui";
import { COPY as C } from "./copy";
import { AUD38 } from "./index";

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(state: Aud38State, close = vi.fn()): ReturnType<typeof vi.fn> {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([
    { path: "/", component: () => <AUD38 workItemId={AUD38_AUDIT_ID} close={close} /> },
  ]);
  return close;
}

async function sheet(): Promise<HTMLElement> {
  const d = await screen.findByRole("dialog", { name: C.title });
  await waitFor(() => {
    expect(d.querySelector("[aria-label='Source']")).not.toBeNull();
  });
  return d;
}

function handOff(d: HTMLElement): HTMLButtonElement {
  return within(d).getByRole<HTMLButtonElement>("button", { name: C.handOff });
}

describe("AUD-38 Hand off to tax", () => {
  it("AUD-38a ready: the fieldsets read the preview and Hand off is enabled", async () => {
    show("a");
    const d = await sheet();
    expect(d.textContent).toContain("Granite Peak Outdoor Supply, Inc. · FY2026 FS audit");
    expect(d.textContent).toContain("Final TB · year ended Jun 30, 2026");
    expect(d.textContent).toContain("Oct 27, 2026 · Margaret Okonkwo");
    expect(d.textContent).toContain(
      "Income before taxes 3,100,000 · tax expense 750,000 · net income 2,350,000",
    );
    expect(d.textContent).toContain(
      "Leo Wong (preparer) · Isaac Moreau (reviewer) · Victor Hammond (partner)",
    );
    expect(d.textContent).toContain("Tax-code mapping · 128 accounts");
    expect(d.textContent).toContain("121 from the prior-year return mapping");
    expect(d.textContent).toContain(
      "6,050,000 + additions 1,380,000 − depreciation 1,050,000 = 6,380,000",
    );
    expect(handOff(d).disabled).toBe(false);
  });

  it("AUD-38 footings: 121 + 5 + 2 = 128 and the book income foots", () => {
    const p = preview("ready");
    expect(p.counts.mapped + p.counts.suggested + p.counts.review).toBe(p.counts.total);
    expect(p.counts.total).toBe(128);
    expect(Number(p.book_income.pretax) - Number(p.book_income.income_tax_expense)).toBe(
      Number(p.book_income.net_income),
    );
    expect(p.accounts?.length).toBe(128);
  });

  it("AUD-38 acceptance: Hand off is the only primary button", async () => {
    show("a");
    const d = await sheet();
    const primaries = [...d.querySelectorAll("button")].filter(
      (b) => b.getAttribute("data-variant") === "primary",
    );
    expect(primaries.map((b) => b.textContent)).toEqual([C.handOff]);
  });

  it("AUD-38 acceptance: focus stays trapped in the sheet", async () => {
    show("a");
    const d = await sheet();
    const close = within(d).getAllByRole("button")[0] as HTMLElement;
    close.focus();
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Tab", shiftKey: true });
    expect(d.contains(document.activeElement)).toBe(true);
    expect(
      d.getAttribute("aria-modal") === "true" || d.closest("[aria-modal='true']") !== null,
    ).toBe(true);
  });

  it("AUD-38b needs review: the banner, amber rows and Hand off disabled until both choose", async () => {
    show("b");
    const d = await sheet();
    expect(within(d).getByText(C.needsReview(2))).toBeTruthy();
    expect(handOff(d).disabled).toBe(true);
    for (const ref of ["2255", "6875"]) {
      const row = d.querySelector(`[data-review='${ref}']`) as HTMLElement;
      expect(row.getAttribute("data-chosen")).toBe("none");
      fireEvent.click(within(row).getByRole("tab", { name: C.mapping.sendBlank }));
    }
    await waitFor(() => {
      expect(handOff(d).disabled).toBe(false);
    });
  });

  it("AUD-38c handed off: the toast words and the TXP-13 banner preview", async () => {
    const shown = vi.spyOn(toast, "show");
    show("c");
    const d = await sheet();
    fireEvent.click(handOff(d));
    const landed = await waitFor(() => {
      const l = d.querySelector<HTMLElement>("[data-aud38='landed']");
      expect(l).not.toBeNull();
      return l as HTMLElement;
    });
    expect(landed.textContent).toContain("From FY2026 audit · Final TB · handed off Nov 9");
    expect(landed.textContent).toContain("by Hannah Leclerc · 10:30 AM");
    expect(landed.textContent).toContain("Book income 2,350,000 · candidate deduction (68,400)");
    expect(within(landed).getByRole("button", { name: C.openTxp13 })).toBeTruthy();
    expect(shown).toHaveBeenCalledWith(
      "Handed off to FY2026 Form 1120 · 1 tax issue created · 7 accounts for the tax team to map",
    );
    shown.mockRestore();
  });

  it("AUD-38d not available: Hand off disabled with the G8 reason", async () => {
    show("d");
    const d = await sheet();
    expect(within(d).getByText(C.notAvailable)).toBeTruthy();
    expect(handOff(d).disabled).toBe(true);
  });

  it("AUD-38e superseded: the amber warning names the version and the tax team", async () => {
    show("e");
    const d = await sheet();
    await waitFor(() => {
      expect(d.querySelector("[data-aud38='superseded']")?.textContent).toBe(
        "The audited TB changed after release (AUD-30). Handing off again replaces the Nov 9 version and notifies Leo Wong, Isaac Moreau and Victor Hammond.",
      );
    });
  });

  it("AUD-38 View all 128 mappings opens the O4 table", async () => {
    show("a");
    const d = await sheet();
    fireEvent.click(within(d).getByRole("button", { name: C.mapping.viewAll(128) }));
    const table = await waitFor(() => {
      const t = document.querySelector("[data-aud38='mappings']");
      expect(t).not.toBeNull();
      return t as HTMLElement;
    });
    expect(table.querySelectorAll("[data-account]").length).toBe(128);
    expect(table.textContent).toContain("Prior-year");
    expect(table.textContent).toContain("Blank");
  });

  it("AUD-38 the agent hands off nothing: no agent-owned approve, send or post", async () => {
    show("a");
    const d = await sheet();
    for (const b of within(d).getAllByRole("button")) {
      expect(b.textContent).not.toMatch(/^(Approve|Sign off|Release|Send|Post)(\s|…|$)/);
    }
  });
});
