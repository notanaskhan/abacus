// C-01-T34 (TASK-8074): CLS-02 Overview A–E in fixture mode. Row acceptance: "State a shows 6 of 9
// and 3 running, d answers only through the named person's click, and the status menu offers In
// review only at 21 of 21."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { copperleafAugust } from "../../fixtures/seed/closes";
import { CLOSE_IDS } from "../../fixtures/seed/closes";
import { newQueryClient } from "../../testing/support";
import { CloseOverview, statusItems } from "./Overview";
import { type ShellState, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const NOW = new Date("2026-09-14T09:24:00-05:00");

function show(state: ShellState, onAnswer?: (a: unknown) => void): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CloseOverview closeId={CLOSE_IDS.august} now={NOW} {...(onAnswer ? { onAnswer } : {})} />
    </QueryClientProvider>,
  );
}

async function frameOf(): Promise<HTMLElement> {
  return waitFor(() => {
    const el = document.querySelector<HTMLElement>("[data-screen='CLS-02'][data-frame]");
    expect(el).not.toBeNull();
    expect(document.querySelector("[data-kit='RunCard']")).not.toBeNull();
    return el as HTMLElement;
  });
}

describe("CLS-02 Overview", () => {
  it("a: Run 2 running, 6 of 9 complete and 3 at once, 2 + 3 + 2 + 1 + 1", async () => {
    show("overview-a");
    await waitFor(() => expect(screen.getByText("6 of 9 complete")).toBeTruthy());
    expect(screen.getByText("3 tasks running at once.")).toBeTruthy();
    expect(screen.getByText("Started 18 minutes ago")).toBeTruthy();
    const groups = [...document.querySelectorAll("[data-group]")].map((g) => g.querySelectorAll("li").length);
    expect(groups).toEqual([2, 3, 2, 1, 1]);
    expect(document.querySelectorAll("li[data-state='run']").length).toBe(3);
  });

  it("b: complete with exceptions at 9:40 AM, 9 of 9 and 7 open", async () => {
    show("overview-b");
    await waitFor(() => expect(screen.getByText("Close agent completed")).toBeTruthy());
    expect(screen.getByText("9 of 9 tasks · 7 open issues · finished 9:40 AM")).toBeTruthy();
  });

  it("c: idle September with Run", async () => {
    show("overview-c");
    const frame = await frameOf();
    expect(frame.dataset.frame).toBe("c");
    expect(screen.getByText(/Ready to run 22 tasks/)).toBeTruthy();
  });

  it("d: the treatment card answers only through a person's click", async () => {
    const onAnswer = vi.fn();
    show("overview-d", onAnswer);
    await waitFor(() => expect(screen.getByText("How should the Aug 31 Square transfer of $6,412.40 be treated?")).toBeTruthy());
    expect(onAnswer).not.toHaveBeenCalled();
    const submit = [...document.querySelectorAll<HTMLButtonElement>("[data-decision] button")].find((b) =>
      (b.textContent ?? "").trim() === "Next",
    );
    expect(submit).toBeDefined();
    fireEvent.click(submit as HTMLButtonElement);
    await waitFor(() => expect(onAnswer).toHaveBeenCalledTimes(1));
  });

  it("e: Stopped at Shopify with Retry and View run", async () => {
    show("overview-e");
    await waitFor(() => expect(screen.getByText("Stopped at Shopify")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "View run" })).toBeTruthy();
  });

  it("offers In review only at 21 of 21", () => {
    const at20 = statusItems({ ...copperleafAugust(), accounts_reconciled: 20 }, () => undefined);
    expect(at20[0]?.disabled).toBe(true);
    const at21 = statusItems({ ...copperleafAugust(), accounts_reconciled: 21 }, () => undefined);
    expect(at21[0]?.disabled).toBe(false);
  });
});
