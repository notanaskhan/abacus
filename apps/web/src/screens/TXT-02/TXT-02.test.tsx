// T-07-T17 (TASK-8077): TXT-02 in fixture mode. Row acceptance: "All scenarios pass, the browser
// never sums (every figure comes from the read model), and no dollar sign renders in the tree."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { CALLOWAY_RETURN } from "../../fixtures/scenarios/TXT-01";
import { newQueryClient } from "../../testing/support";
import { type TXT02Props, TXT02 } from "./index";
import { type CalcScenario, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: CalcScenario, props: Partial<TXT02Props> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <TXT02 returnId={CALLOWAY_RETURN} {...props} />
    </QueryClientProvider>,
  );
}

const tree = async (): Promise<HTMLElement> =>
  waitFor(() => {
    const el = document.querySelector<HTMLElement>("[data-screen='TXT-02'][data-version]");
    expect(el).not.toBeNull();
    return el as HTMLElement;
  });

describe("TXT-02 Trust Calculation", () => {
  it("a: the tree, Nora's DNI allocated lit, the tie, and no $ anywhere", async () => {
    show("a");
    const el = await tree();
    expect(el.textContent).not.toContain("$");
    expect(
      document.querySelector("[data-row='nora_dni'] [data-highlighted='true']"),
    ).not.toBeNull();
    expect(document.querySelector("[data-tally='k1_tie']")?.textContent).toContain("tie");
    expect(document.querySelector("[data-row='taxable']")?.textContent).toContain("159,900");
    expect(document.querySelector("[data-row='trustee_fees']")?.textContent).toContain("(30,000)");
  });

  it("b: collapsed overview shows the four top rows", async () => {
    show("b", { initial: { collapsed: true } });
    await tree();
    const top = document.querySelectorAll("[data-level='0']");
    expect(top.length).toBe(4);
    expect([...document.querySelectorAll("[aria-expanded='true']")].length).toBe(0);
  });

  it("c: by character reads Interest 100,000 · 40,000 · 20,000 · 40,000", async () => {
    show("c", { initial: { view: "character" } });
    await tree();
    const row = await waitFor(() => {
      const r = document.querySelector("[data-character='interest']");
      expect(r).not.toBeNull();
      return r as HTMLElement;
    });
    expect([...row.querySelectorAll("td")].map((t) => t.textContent)).toEqual([
      "Interest",
      "100,000",
      "40,000",
      "20,000",
      "40,000",
    ]);
  });

  it("d: Theo's edit shows 260,000 / 140,000 / 139,900 with struck priors and Re-approve", async () => {
    show("d");
    await tree();
    expect(document.querySelector("[data-row='paid']")?.textContent).toContain("260,000");
    expect(document.querySelector("[data-row='undistributed']")?.textContent).toContain("140,000");
    expect(document.querySelector("[data-row='taxable'] [data-prior]")?.textContent).toBe(
      "159,900",
    );
    expect(document.querySelector("[data-row='taxable']")?.textContent).toContain("139,900");
    expect(document.querySelectorAll("[data-changed]").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Re-approve…" })).toBeTruthy();
  });

  it("e: signed off reads Reviewed · SI", async () => {
    show("e");
    await tree();
    expect(document.querySelector("[data-reviewed]")?.textContent).toBe("Reviewed · SI");
  });

  it("f1: waiting on the interpretation", async () => {
    show("f1");
    expect(
      await screen.findByText("Approve the instrument interpretation to compute DNI."),
    ).toBeTruthy();
  });

  it("a chevron closes a branch", async () => {
    show("a");
    await tree();
    const fai = document.querySelector<HTMLButtonElement>(
      "[data-row='fai'] > div [aria-expanded]",
    );
    expect(fai?.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(fai as HTMLButtonElement);
    expect(fai?.getAttribute("aria-expanded")).toBe("false");
  });

  it("T-07-T21: ?row= lights the row TXT-01's Cited by named", async () => {
    show("a", { row: "dni" });
    await tree();
    expect(
      document.querySelector("[data-row='dni'] > div[data-highlighted='true']"),
    ).not.toBeNull();
  });
});
