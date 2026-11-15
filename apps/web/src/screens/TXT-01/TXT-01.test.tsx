// TXT-01 · Review › Instrument (T-07-T15; SPEC-656 AC-1.1 to AC-5.2). Acceptance (the task row):
// "All ten scenarios pass their checklists, hovering IV(a) scrolls to and lights Art. IV(a) within
// 360 ms (instantly under reduced motion), and every clause-governed determination shows its chip."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { TXT01 } from ".";
import { COPY } from "./copy";
import {
  CALLOWAY_RETURN,
  CLICK_PASSAGE,
  HOVER_CHIP,
  type Txt01State,
  scenarios,
} from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function mount(state: Txt01State, props: Partial<Parameters<typeof TXT01>[0]> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([{ path: "/", component: () => <TXT01 returnId={CALLOWAY_RETURN} {...props} /> }]);
}

const GOVERNED = [
  "grantor_status",
  "trust_type",
  "fai_definition",
  "trustee_fees",
  "principal_invaded",
];

function row(key: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-determination="${key}"]`);
  if (found === null) throw new Error(`no row ${key}`);
  return found;
}

describe("TXT-01", () => {
  it("a: proposed, seven determinations, every governed one with its clause chip", async () => {
    mount("a");
    await screen.findByText("Non-grantor: no retained powers under §§673–677; settlor deceased");
    expect(document.querySelectorAll("[data-determination]")).toHaveLength(7);
    for (const key of GOVERNED) {
      expect(row(key).querySelectorAll("[data-chip]").length).toBeGreaterThan(0);
    }
    expect(screen.getByText(COPY.proposedByAgent)).toBeTruthy();
    expect(row("trust_type").dataset.lit).toBe("true");
    expect(
      screen.getByText(/Read by Accrued Agent Sep 3 · 7 determinations · 6 clause citations/),
    ).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelector('[data-lit="true"]')).toBeTruthy();
    });
  });

  it("a2: hovering IV(a) lights Art. IV(a) and scrolls to it at once", async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    mount("a2");
    await screen.findByText("Trust type this year");
    await screen.findByText(/Any net income not distributed/);
    const chip = within(row("trust_type")).getByRole("button", { name: "IV(a)" });
    fireEvent.mouseEnter(chip);
    await waitFor(() => {
      const lit = document.querySelector(`[data-clause="${HOVER_CHIP}"] [data-lit="true"]`);
      expect(lit).toBeTruthy();
    });
    expect(scroll).toHaveBeenCalled();
  });

  it("a3: clicking Art. II lists the determinations that cite it", async () => {
    mount("a3");
    const passage = await screen.findByText(/Gains from the sale or exchange of trust assets/);
    fireEvent.click(passage);
    const popover = await screen.findByRole("dialog", { name: COPY.reader.citedBy });
    expect(popover.dataset.passagePopover).toBe(CLICK_PASSAGE);
    expect(within(popover).getByText("Fiduciary accounting income")).toBeTruthy();
  });

  it("a4: Approve interpretation opens SHL-12", async () => {
    const approve = vi.fn();
    mount("a4", { onApprove: approve });
    const button = await screen.findByRole("button", { name: COPY.approve });
    fireEvent.click(button);
    expect(approve).toHaveBeenCalledTimes(1);
  });

  it("b: approved, locked, the button disabled", async () => {
    mount("b");
    const button = await screen.findByRole("button", { name: COPY.approved });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(await screen.findByText(/Approved · Samuel Ito · Sep 14/)).toBeTruthy();
  });

  it("c: principal invaded shows the banner, the note and Yes — 25,000 (HEMS)", async () => {
    mount("c");
    expect(
      await screen.findByText(
        "Scenario: 25,000 of principal paid for Theo's tuition under Art. IV(b)",
      ),
    ).toBeTruthy();
    expect(screen.getByText(/Nora 160,000 · Theo 105,000 · trust retains 135,000/)).toBeTruthy();
    expect(within(row("principal_invaded")).getByText("Yes — 25,000 (HEMS)")).toBeTruthy();
  });

  it("d: unread offers Read instrument and lights nothing", async () => {
    mount("d");
    expect(await screen.findByText(COPY.unread.title)).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.unread.read })).toBeTruthy();
    expect(document.querySelector('[data-lit="true"]')).toBeNull();
  });

  it("d1: agents off records each row and never offers Read instrument", async () => {
    mount("d1");
    await screen.findByText(COPY.agentsOff);
    expect(screen.getAllByRole("button", { name: COPY.record })).toHaveLength(7);
    expect(screen.queryByRole("button", { name: COPY.unread.read })).toBeNull();
  });

  it("d2: reading shows the run's progress", async () => {
    mount("d2");
    expect(await screen.findByText("Checking citation 4 of 6")).toBeTruthy();
  });

  it("d3: consent required names the trust and the consents signed", async () => {
    mount("d3");
    expect(await screen.findByText(/§7216 AI consent — .*\(1 of 2 signed\)/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: COPY.unread.read })).toBeNull();
  });
});
