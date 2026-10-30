// KNW-04 j · Deadline rules (K-02-T17; DF-10; K-02 F6 US-6.1). The acceptance: "Each table shows its
// reference-set version, effective date and source, and no firm role sees an edit control." Axe,
// parity and the journeys are K-02-T19's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { REFERENCE_SETS } from "../../fixtures/seed/reference-sets";
import { newQueryClient } from "../../testing/support";
import { KNW04 } from ".";
import { OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(persona?: string): void {
  restore = installFixtureMode(scenarios.j, persona === undefined ? {} : { persona });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <KNW04 initial={OPENS.j} />
    </QueryClientProvider>,
  );
}

async function sets(): Promise<HTMLElement[]> {
  await waitFor(() => {
    expect(document.querySelectorAll("[data-reference-set]")).toHaveLength(6);
  });
  return [...document.querySelectorAll<HTMLElement>("[data-reference-set]")];
}

describe("KNW-04 j · Deadline rules (Grace Holloway)", () => {
  it("lists the six reference-set kinds in order", async () => {
    show();
    const kinds = (await sets()).map((s) => s.getAttribute("data-kind"));
    expect(kinds).toEqual([
      "due_date_rules",
      "legal_holidays",
      "disaster_postponements",
      "form_8879_set",
      "information_return_thresholds",
      "retention_minimums",
    ]);
  });

  it("each table shows its version, effective date and source", async () => {
    show();
    for (const set of await sets()) {
      expect(set.querySelector("[data-version-chip]")?.textContent).toBe("v1");
      expect(set.querySelector("[data-effective]")?.textContent).toMatch(
        /^Effective [A-Z][a-z]{2} \d{1,2}, \d{4}$/u,
      );
      expect(set.querySelector("[data-source]")?.textContent).toMatch(/^Source: .+ — verify$/u);
      expect(within(set).getByText("Published")).toBeTruthy();
    }
  });

  it("draws the rows the server resolved: due dates, holidays, 8879 forms and tolerances, thresholds, retention", async () => {
    show();
    await sets();
    const due = screen.getByRole("table", { name: "Federal due-date rules · TY2025" });
    expect(within(due).getAllByRole("row")).toHaveLength(7);
    expect(due.textContent).toContain("15th day of the 4th month");
    expect(due.textContent).toContain("Form 4868 · 6 months");
    expect(due.textContent).toContain("Form 7004 · 5 months, to the 30th");
    expect(screen.getByText("District of Columbia Emancipation Day")).toBeTruthy();
    expect(screen.getByText("No postponements in effect.")).toBeTruthy();
    const tolerances = screen.getByRole("table", { name: "Pub 1345 tolerances" });
    expect(tolerances.textContent).toContain("$50");
    expect(tolerances.textContent).toContain("$14");
    expect(screen.getByText("8879-PE")).toBeTruthy();
    expect(screen.getByText("1099-NEC")).toBeTruthy();
    expect(screen.getByText("AU-C 230")).toBeTruthy();
    expect(REFERENCE_SETS).toHaveLength(6);
  });

  it.each(["grace-holloway", "priya-raman", "daniel-reyes", "cole-hart"])(
    "no edit control for %s",
    async (persona) => {
      show(persona);
      await sets();
      const page = document.querySelector("[data-screen='KNW-04']") as HTMLElement;
      expect(within(page).queryAllByRole("button")).toHaveLength(0);
      expect(within(page).queryAllByRole("textbox")).toHaveLength(0);
      expect(screen.queryByRole("button", { name: "New version…" })).toBeNull();
      expect(screen.queryByRole("button", { name: /Publish/u })).toBeNull();
    },
  );
});
