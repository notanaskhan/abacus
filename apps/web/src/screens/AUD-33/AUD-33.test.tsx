import { client } from "@abacus/api-client/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { AUD33, type Aud33Mode } from ".";
import { COPY } from "./copy";
import {
  AUD33_CONSOLIDATION,
  AUD33_WORK_ITEM,
  type Aud33State,
  STATES,
  scenarios,
} from "./scenarios";

// A-09-T15 (TASK-8096; SPEC-658; handoff AUD-33): "AUD-33 a-g match their scenarios at Tier C, no
// total is summed in the browser, and Approve is disabled with Off 10,000 in c."

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});
let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function wrap(node: ReactNode): JSX.Element {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queries}>{node}</QueryClientProvider>;
}

const MODE: Record<Aud33State, Aud33Mode> = {
  a: "posted",
  b: "proposed",
  c: "off",
  d: "posted",
  e: "adjustments",
  f: "locked",
  g: "entity",
}; // fmt: skip

async function at(state: Aud33State): Promise<void> {
  restore = installFixtureMode(scenarios[state]);
  render(
    wrap(
      <AUD33
        workItemId={AUD33_WORK_ITEM}
        consolidationId={AUD33_CONSOLIDATION}
        level={state === "d" ? 2 : 1}
        mode={MODE[state]}
      />,
    ),
  );
  await screen.findByRole("table", { name: COPY.pane });
}

describe("AUD-33 Consolidated trial balance", () => {
  it("has the seven states", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
  });

  it("a: the server's tallies, six posted cards and 67,840,000 Dr = Cr", async () => {
    await at("a");
    const strip = screen.getByRole("list", { name: COPY.tallies.label });
    expect(within(strip).getAllByText("50,760,000").length).toBe(2); // total assets and the BALANCED tie
    expect(document.querySelectorAll('[data-elimination][data-status="posted"]')).toHaveLength(6);
    expect(document.querySelector("[data-drawer-total]")?.textContent).toContain("67,840,000");
    expect(
      document.querySelector('[data-row="Inventory"] [data-column="consolidated"]')?.textContent,
    ).toBe("15,660,000");
    expect(document.querySelector('[data-row="Inventory"] [data-tag="E3"]')).not.toBeNull();
  });

  it("b: proposed cards carry the person's Approve, and the tallies read Pending", async () => {
    await at("b");
    expect(document.querySelectorAll('[data-elimination][data-status="proposed"]')).toHaveLength(
      6,
    );
    expect(screen.getAllByText(COPY.tallies.pending).length).toBe(2);
    expect(screen.getByRole("button", { name: COPY.drawer.approveAll(6) })).toBeDefined();
  });

  it("c: Approve is disabled with Off 10,000 on E3", async () => {
    await at("c");
    const e3 = document.querySelector('[data-elimination="E3"]') as HTMLElement;
    expect(e3.querySelector("[data-off]")?.textContent).toBe("Off 10,000 · debits ≠ credits");
    expect(
      within(e3).getByRole<HTMLButtonElement>("button", { name: COPY.card.approve }).disabled,
    ).toBe(true);
    expect(screen.getByText("off 10,000")).toBeDefined();
  });

  it("d: Level 2 shows Operating Co.'s three entities", async () => {
    await at("d");
    expect(document.querySelector('[data-level="2"]')).not.toBeNull();
    expect(screen.getByText(COPY.captionTwo)).toBeDefined();
  });

  it("e, f, g: adjustments empty, locked with Reopen, the entity tab", async () => {
    await at("e");
    expect(document.querySelector("[data-adjustments-empty]")).not.toBeNull();
    cleanup();
    restore?.();
    await at("f");
    expect(screen.getByRole("button", { name: COPY.reopen })).toBeDefined();
    cleanup();
    restore?.();
    await at("g");
    expect(document.querySelectorAll("[data-worksheet] thead th")).toHaveLength(2);
  });

  it("a tag selects its card", async () => {
    await at("a");
    fireEvent.click(
      document.querySelector(
        '[data-row="Intercompany receivable"] [data-tag="E4"]',
      ) as HTMLElement,
    );
    expect(document.querySelector('[data-elimination="E4"]')?.getAttribute("aria-selected")).toBe(
      "true",
    );
  });
});
