// A-05-T23 (TASK-3235): EBP-03 a–e in fixture mode inside the AUD-02 cockpit. Row acceptance: "The
// 25 sampled participants appear in A-03 order with Alicia Brennan first, exceptions use the Flag
// and pill only, and the viewer never shows a Form I-9." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { EBP03Frame } from "./artboard";
import { type Ebp03State, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Ebp03State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <EBP03Frame state={state} />
    </QueryClientProvider>,
  );
}

const matrix = (): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>("[data-ebp03='matrix']");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

describe.each(STATES)("EBP-03 %s", (state) => {
  it("renders its 25 rows in A-03 order, Alicia Brennan first", async () => {
    show(state);
    const grid = await matrix();
    const names = [...grid.querySelectorAll("[data-participant]")].map((r) =>
      r.getAttribute("data-participant"),
    );
    expect(names).toHaveLength(25);
    expect(names[0]).toBe("Alicia Brennan");
    expect(document.body.textContent).not.toMatch(/I-9/u);
  });
});

describe("EBP-03 exceptions", () => {
  it("a: the Flag records one AUD-15 draft finding under the handoff's title", async () => {
    show("a");
    const grid = await matrix();
    const flags = within(grid).getAllByRole("button", { name: "Flag to a draft finding" });
    expect(flags).toHaveLength(2);
    fireEvent.click(flags[0] as HTMLElement);
    await waitFor(() => {
      expect(
        within(grid).queryAllByRole("button", { name: "Flag to a draft finding" }),
      ).toHaveLength(0);
    });
  });

  it("a: shows the plan's auto-enrollment and auto-escalation provisions", async () => {
    show("a");
    await matrix();
    const cards = await waitFor(() => {
      const found = document.querySelectorAll("[data-ebp03='provisions']");
      expect(found.length).toBe(2);
      return found;
    });
    expect(cards[0]?.textContent).toContain("Auto-Enrollment Provisions");
    expect(cards[1]?.textContent).toContain("Auto-Escalation Provisions");
  });
});

describe("EBP-03 results", () => {
  it("a: two exceptions use the Flag and the Exception pill only", async () => {
    show("a");
    const grid = await matrix();
    const flagged = [...grid.querySelectorAll("[data-ebp03='exception']")].map((e) =>
      e.closest("[data-participant]")?.getAttribute("data-participant"),
    );
    expect(flagged).toEqual(["Kwame Mensah", "Yuki Mori"]);
    for (const row of grid.querySelectorAll("tr[data-row]")) {
      expect(row.className).not.toMatch(/bg-red/u);
    }
    expect(document.body.textContent).toContain("Exceptions · 2 in sample");
  });

  it("a: dates of birth are masked and the computation line names no birthday", async () => {
    show("a");
    const grid = await matrix();
    expect(grid.textContent).toContain("••/••/••••");
    expect(grid.textContent).not.toContain("03/14/1990");
    expect(document.querySelector("[data-ebp03='computation']")?.textContent).toContain(
      "hire + 3 months = 05/10/2025 → entry 06/01/2025",
    );
  });

  it("a: a verified rule shows no entry-rule notice", async () => {
    show("a");
    await matrix();
    expect(document.querySelector("[data-ebp03='entry-rule']")).toBeNull();
  });

  it("f: with the entry rule unverified the rows show no entry date and no computation", async () => {
    show("f");
    const grid = await matrix();
    expect(document.querySelector("[data-ebp03='entry-rule']")?.textContent).toContain(
      "must be verified on EBP-02",
    );
    expect(grid.textContent).not.toContain("06/01/2025");
    expect(document.querySelector("[data-ebp03='computation']")).toBeNull();
    expect(document.querySelector("[data-ebp03='exceptions']")?.textContent).not.toContain(
      "2,472",
    );
  });

  it("b: untested rows spin while the agent tests", async () => {
    show("b");
    const grid = await matrix();
    expect(grid.querySelectorAll("[data-ebp03='testing']").length).toBe(19);
  });

  it("c: row 22 needs a human until Ana marks it no effect", async () => {
    show("c");
    const grid = await matrix();
    const mark = await waitFor(() => {
      const found = [...grid.querySelectorAll("button")].find((b) =>
        b.textContent.includes("Mark no effect"),
      );
      expect(found).toBeDefined();
      return found as HTMLButtonElement;
    });
    fireEvent.click(mark);
    await waitFor(() => {
      expect(document.querySelector("[data-ebp03='needs-human']")).toBeNull();
    });
  });

  it("d and e: the header chips read ✓ AC, then ✓ AC ✓ HL", async () => {
    show("e");
    await matrix();
    await waitFor(() => {
      expect(document.querySelector("[data-chip='l1']")?.textContent).toBe("✓ AC");
      expect(document.querySelector("[data-chip='l2']")?.textContent).toBe("✓ HL");
    });
  });
});
