import { client } from "@abacus/api-client/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { AUD32 } from ".";
import { COPY } from "./copy";
import {
  AUD32_CONSOLIDATION,
  AUD32_WORK_ITEM,
  type Aud32State,
  STATES,
  STEP_OF,
  scenarios,
} from "./scenarios";

// A-09-T14 (TASK-8095; SPEC-658; handoff AUD-32): "AUD-32 a-f match their scenarios at Tier C with
// Next disabled and its reason in a and interim debits 187,860,000 in d."

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

async function at(state: Aud32State): Promise<void> {
  restore = installFixtureMode(scenarios[state]);
  render(
    wrap(
      <AUD32
        workItemId={AUD32_WORK_ITEM}
        consolidationId={AUD32_CONSOLIDATION}
        step={STEP_OF[state]}
      />,
    ),
  );
  await screen.findByRole("dialog", { name: COPY.title });
}

describe("AUD-32 Consolidation setup", () => {
  it("has the six states", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("a: Next is disabled with its reason while Real Estate Prior is missing", async () => {
    await at("a");
    const next = screen.getByRole("button", { name: COPY.next });
    expect((next as HTMLButtonElement).disabled).toBe(true);
    expect(document.querySelector("[data-footer]")?.textContent).toBe(
      "9 of 10 trial balances attached · missing: Harlow & Pike Real Estate, LLC · Prior",
    );
    expect(document.querySelectorAll('[data-slot][data-state="missing"]')).toHaveLength(1);
  });

  it("a to d: Mark not needed needs a reason and then the step can move on", async () => {
    await at("a");
    fireEvent.click(screen.getByRole("button", { name: COPY.markNotNeeded }));
    const confirm = screen.getByRole("button", { name: COPY.confirmNotNeeded });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(COPY.reason), { target: { value: "Formed Jan 2026" } });
    fireEvent.click(confirm);
    await waitFor(() => {
      expect(screen.getByRole<HTMLButtonElement>("button", { name: COPY.next }).disabled).toBe(
        false,
      );
    });
  });

  it("d: the review totals 187,860,000 and Finalize is the manager's", async () => {
    await at("d");
    expect(document.querySelector("[data-total]")?.textContent).toBe("187,860,000");
    expect(screen.getByText(COPY.review.summary(5, 3, 10))).toBeDefined();
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: COPY.review.finalize }).disabled,
    ).toBe(false);
  });

  it("e: finalized", async () => {
    await at("e");
    expect(document.querySelector('[data-status="finalized"]')).not.toBeNull();
  });

  it("f: the Distribution interim needs reauth, with the reconnection request", async () => {
    await at("f");
    expect(screen.getByText(COPY.needsReauth)).toBeDefined();
    expect(screen.getByRole("button", { name: COPY.requestReconnection })).toBeDefined();
  });

  it("b and c: details and the proposed structure", async () => {
    await at("b");
    expect(screen.getByText(COPY.details.interimValue)).toBeDefined();
    cleanup();
    restore?.();
    await at("c");
    expect(document.querySelector("[data-agent-banner]")).not.toBeNull();
    expect(document.querySelectorAll("[data-step=structure] [data-entity]")).toHaveLength(5);
  });
});
