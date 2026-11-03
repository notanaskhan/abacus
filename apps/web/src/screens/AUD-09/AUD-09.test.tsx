// A-04-T32 (TASK-3273): AUD-09 a–f and the C-20 states in fixture mode. Row acceptance: "AUD-09 a-e
// render live at Tier C and f from fixtures until A-06 registers, the failed state quotes the run
// error verbatim, and no control sets a concluded severity." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { KNW03_RUN_ERROR } from "../../fixtures/seed/knw03";
import { newQueryClient } from "../../testing/support";
import { AuditCockpitPage } from "../AUD-02";
import type { ControlsOptions } from "./Controls";
import { type Aud09State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Aud09State, controls: ControlsOptions = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AuditCockpitPage
        auditId={NORTHWIND_AUDIT}
        initial={{ section: "internal_control", controls }}
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

const COSO = [
  "Control environment",
  "Risk assessment",
  "Control activities",
  "Information & communication",
  "Monitoring",
];

describe("AUD-09", () => {
  it("a: Exceptions!B1:E8, header row 1, data rows 2–8, 1 + 3 + 3 = 7", async () => {
    show("a");
    await drawn("[data-sheet-row='8']");
    const rows = [...document.querySelectorAll<HTMLElement>("[data-sheet-row]")].map(
      (r) => r.dataset.sheetRow,
    );
    expect(rows).toEqual(["1", "2", "3", "4", "5", "6", "7", "8"]);
    expect(document.querySelector("[data-cell='C1']")?.textContent).toBe("Description");
    expect(document.querySelectorAll("[data-proposed='significant_deficiency']").length).toBe(1);
    expect(document.querySelectorAll("[data-proposed='deficiency']").length).toBe(3);
    expect(document.querySelectorAll("[data-disposition='exception_for_resolution']").length).toBe(
      3,
    );
    // The severity column holds only AU-C 265 words or the disposition; COSO sits in column E.
    for (const n of [2, 3, 4, 5, 6, 7, 8]) {
      const d = document.querySelector(`[data-cell='D${String(n)}']`)?.textContent ?? "";
      for (const word of COSO) expect(d).not.toContain(word);
    }
    expect(document.querySelector("[data-cell='E2']")?.textContent).toBe("Control activities");
    expect(document.querySelector("[data-cell='C2']")?.textContent).toContain(
      "The Dec 26, 2025 payroll deferrals and match ($48,600) reached Harborline on Jan 9, 2026",
    );
    expect(document.querySelector("[data-cell='C7']")?.textContent).toContain(
      "3 terminated participants' loans ($14,850)",
    );
    expect(document.querySelector("[data-cell='C6']")?.textContent).toContain(
      "4 auto-enrolled employees",
    );
    const footer = await drawn("[data-aud09='footer']");
    expect(footer.textContent).toBe("No evidence is linked to Exceptions!C1.");
  });

  it("b: D2 selected, the footer names its two citations", async () => {
    show("b", { cell: "D2" });
    await waitFor(
      () => {
        expect(document.querySelector("[data-aud09='footer']")?.textContent).toBe(
          "Exceptions!D2 · 2 citations — PayGrid Contribution Detail 2025.xlsx (pay date 12/26/2025) · Keystone Account Balances PY2025.xlsx (deposit 1/9/2026)",
        );
      },
      { timeout: 6000 },
    );
  });

  it("c: the O1 picker proposes; concluding is the partner's", async () => {
    show("c", { cell: "D2", initialPicker: "D2" });
    const picker = await drawn("[data-aud09='picker']");
    const choices = [...picker.querySelectorAll<HTMLElement>("[data-choice]")].map(
      (b) => b.textContent,
    );
    expect(choices).toEqual(["Deficiency", "Significant deficiency", "Material weakness"]);
    expect(picker.textContent).toContain(
      "Proposed by Accrued Agent. Concluding severity is reserved to the engagement partner (Findings).",
    );
    expect(document.body.textContent).not.toMatch(/\bConclude\b/);
  });

  it("d: the seeded failure quotes the run error verbatim; the grid keeps its header", async () => {
    show("d");
    const error = await drawn("[data-aud09='run-error']");
    expect(error.textContent).toBe(KNW03_RUN_ERROR);
    const step = await drawn("[data-aud09='failed-step']");
    expect(step.textContent).toContain("Retry");
    expect([...document.querySelectorAll("[data-sheet-row]")].length).toBe(1);
    expect(document.querySelector("[data-aud09='footer']")?.textContent).toBe(
      "No evidence written.",
    );
  });

  it("e: Internal Control lists five processes × walkthrough, design, implementation, reliance", async () => {
    show("e", { sheet: "internal-control" });
    const table = await drawn("[data-aud09='processes']");
    await waitFor(() => {
      expect(table.querySelectorAll("[data-process]").length).toBe(5);
    });
    const data = table.querySelector("[data-process='Participant data changes']")?.textContent;
    expect(data).toContain("Deficient");
    expect(data).toContain("Not implemented");
    await waitFor(() => {
      expect(table.querySelector("[data-process='Investment elections']")?.textContent).toContain(
        "Keystone SOC 1",
      );
    });
  });

  it("f: D2 concluded by the partner and communicated, never amber", async () => {
    show("f");
    const concluded = await drawn("[data-concluded='significant_deficiency']");
    expect(concluded.className).not.toContain("amber");
    expect(concluded.className).toContain("font-medium");
    expect(document.querySelector("[data-cell='D2'] [data-communicated]")).not.toBeNull();
    // Margaret's read-through offers no picker: the conclusion is A-06's record.
    fireEvent.doubleClick(document.querySelector("[data-cell='D2']") as HTMLElement);
    expect(document.querySelector("[data-aud09='picker']")).toBeNull();
  });

  it("off: assurance.internal_control off draws C-20, never the grid", async () => {
    show("off");
    await waitFor(
      () => {
        expect(document.body.textContent).toContain("not turned on");
      },
      { timeout: 6000 },
    );
    expect(document.querySelector("[data-aud09='grid']")).toBeNull();
  });
});
