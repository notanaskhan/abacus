// T-03-T11 (TASK-3324): TAX-13 in fixture mode. Row: "TAX-13a, b and c render in fixture mode with
// tallies footing, no dollar signs in cells and Thornbury's Prepare 4768 action disabled with the gate
// to clear."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { Extensions, type ExtensionsProps } from "./Extensions";
import { type Tax13State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Tax13State, props: Partial<ExtensionsProps> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Extensions taxYear={2025} {...props} />
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

const count = (tile: string): number =>
  Number(document.querySelector(`[data-tile='${tile}'] span:last-child`)?.textContent);

describe("TAX-13", () => {
  it("a: the tallies foot, 79 + 82 = 161", async () => {
    show("a");
    await drawn("[data-tax13='extensions'] tbody tr");
    expect(count("open") + count("filed")).toBe(count("extended"));
    expect(count("extended")).toBe(161);
    expect(count("likely")).toBe(2);
  });

  it("a: no dollar signs in cells, and tomorrow's due is urgent", async () => {
    show("a");
    const table = await drawn("[data-tax13='extensions']");
    await waitFor(() => {
      expect(table.textContent).toContain("Ridgeline Property Partners");
    });
    expect(table.textContent).not.toContain("$");
    const row = document.querySelector("[data-client^='Ridgeline']");
    expect(row?.querySelector("[data-due='urgent']")?.textContent).toContain("1 day");
    expect(row?.querySelector("[data-col='paid']")?.textContent).toContain("IL 28,044");
  });

  it("b: Q3 installments foot to 5 due, with Resend on those awaiting", async () => {
    show("b", { tab: "estimates", taxYear: 2026 });
    const table = await drawn("[data-tax13='estimates'] tbody tr");
    expect(table).toBeTruthy();
    expect(count("paid") + count("scheduled") + count("confirmation_requested")).toBe(
      count("due"),
    );
    expect(count("not_required")).toBe(2);
    expect(document.querySelectorAll("[data-tax13='estimates'] button")).toHaveLength(2);
  });

  it("c: Thornbury's Prepare 4768… is disabled with the gate; Lakeshore's is enabled", async () => {
    show("c", { segment: "likely" });
    await drawn("[data-client='Lakeshore Literacy Alliance']");
    const thornbury = document.querySelector("[data-client='Estate of Walter Thornbury']");
    const blocked = thornbury?.querySelector("[data-blocked]");
    expect(blocked?.getAttribute("data-blocked")).toContain("G1 and G3");
    expect(blocked?.querySelector("button")?.hasAttribute("disabled")).toBe(true);
    const lakeshore = document.querySelector("[data-client='Lakeshore Literacy Alliance']");
    const prepare = Array.from(lakeshore?.querySelectorAll("button") ?? []).find((b) =>
      b.textContent.includes("Prepare 8868"),
    );
    expect(prepare?.hasAttribute("disabled")).toBe(false);
  });
});

describe("T-03-T11: Open in Excel", () => {
  it("fetches the view's workbook and hands it to the browser", async () => {
    const created = vi.fn((_: Blob) => "blob:tax13");
    Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() });
    show("a");
    const button = await waitFor(
      () => {
        const found = [...document.querySelectorAll("button")].find(
          (b) => b.textContent === "Open in Excel",
        );
        expect(found).toBeDefined();
        return found as HTMLButtonElement;
      },
      { timeout: 6000 },
    );
    button.click();
    await waitFor(() => {
      expect(created).toHaveBeenCalledOnce();
    });
  });
});
