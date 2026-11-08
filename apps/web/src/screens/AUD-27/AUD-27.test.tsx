// A-05-T57 (TASK-6213): AUD-27 in fixture mode. Row: "Status words are only Unevaluated, Evaluated
// and Exception (plus a muted Screened out), and the agent never shows a conclusion."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { AUD27_WORK_ITEM, PEAKLINE } from "../../fixtures/seed/aud27";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { type Aud27Tab, type EngagementKind, useEstimatesCanvas } from "./Estimates";
import { type Aud27State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const ALLOWED = new Set([
  "Unevaluated",
  "Evaluated",
  "Evaluated · pending EP",
  "Exception",
  "Screened out",
]);
const CONCLUSIONS = /\b(is a related party|is not a related party|concluded|conclusion:)/i;

function Canvas({ tab, kind }: { tab: Aud27Tab; kind: EngagementKind }): JSX.Element {
  const canvas = useEstimatesCanvas(AUD27_WORK_ITEM, { tab, kind });
  return (
    <div>
      {canvas.controls}
      {canvas.children}
      {canvas.footer}
    </div>
  );
}

function show(state: Aud27State, tab: Aud27Tab, kind: EngagementKind = "fs"): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Canvas tab={tab} kind={kind} />
    </QueryClientProvider>,
  );
}

function pills(): string[] {
  return [...document.querySelectorAll("td span")]
    .map((n) => n.textContent)
    .filter((t) => ALLOWED.has(t) || /Unevaluated|Evaluated|Exception|Screened out/.test(t));
}

describe("AUD-27", () => {
  it("a: the inventory reserve is pending the EP with its method, bias and disclosure", async () => {
    show("a", "estimates");
    await waitFor(() => {
      expect(document.querySelector('[data-aud27="method"]')).not.toBeNull();
    });
    const table = document.querySelector('[data-aud27="estimates"]');
    expect(table?.textContent).toContain("$486,000.00");
    expect(table?.textContent).toContain("Evaluated · pending EP");
    expect(document.querySelector("[data-tie]")?.getAttribute("data-tie")).toBe("ties");
    expect(document.querySelector('[data-aud27="bias"]')?.textContent).toContain("less than 6%");
    expect(document.body.textContent).toContain(COPY.requestConclusion);
  });

  it("d: every estimate is unevaluated and no method card shows", async () => {
    show("d", "estimates");
    await waitFor(() => {
      expect(document.querySelector('[data-aud27="estimates"]')).not.toBeNull();
    });
    expect(document.querySelector('[data-aud27="method"]')).toBeNull();
    expect(new Set(pills())).toEqual(new Set(["Unevaluated"]));
  });

  it.each([
    ["b", "related_parties", "fs"],
    ["e", "related_parties", "fs"],
    ["c", "parties_in_interest", "ebp"],
  ] as const)(
    "%s: only the registry's words, and the agent never concludes",
    async (state, tab, kind) => {
      show(state, tab, kind);
      await waitFor(() => {
        expect(document.querySelector(`[data-aud27="${tab}"]`)).not.toBeNull();
      });
      for (const word of pills()) expect(ALLOWED.has(word)).toBe(true);
      expect(document.body.textContent).not.toMatch(CONCLUSIONS);
    },
  );

  it("b: Peakline is an exception with Ask management; e links Finding F-3", async () => {
    show("b", "related_parties");
    await waitFor(() => {
      expect(document.querySelector(`[data-party="${PEAKLINE}"]`)).not.toBeNull();
    });
    const row = document.querySelector(`[data-party="${PEAKLINE}"]`);
    expect(row?.getAttribute("data-status")).toBe("exception");
    expect(row?.querySelector('[data-action="ask"]')?.textContent).toBe(
      COPY.related.askManagement,
    );
    cleanup();
    restore?.();
    show("e", "related_parties");
    await waitFor(() => {
      expect(document.querySelector('[data-action="finding"]')?.textContent).toBe(
        COPY.related.finding,
      );
    });
  });

  it("c: the late remittance reads as a prohibited transaction on line 4a", async () => {
    show("c", "parties_in_interest", "ebp");
    await waitFor(() => {
      expect(document.querySelector('[data-aud27="prohibited"]')).not.toBeNull();
    });
    const card = document.querySelector('[data-aud27="prohibited"]');
    expect(card?.textContent).toContain("$64.38");
    expect(card?.textContent).toContain(COPY.pii.scheduleGNote);
  });

  it("a: picking an estimate selects it", async () => {
    show("a", "estimates");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-estimate]").length).toBe(3);
    });
    const warranty = [...document.querySelectorAll("[data-estimate]")][1] as Element;
    fireEvent.click(warranty);
    expect(warranty.hasAttribute("data-selected")).toBe(true);
  });
});
