// P-04-T51 (ADR-078, independent): acceptance tests for the SHL-12 UI written from the P-04 spec
// and the C3 contract, not from the screen's code. "Tests pass and fail if a stale sign-off can be
// kept or a denied level offered." Blocked states are stated in words, the level picker offers
// exactly the levels the server allows, a stale sign-off offers only Re-sign, bulk shows a result
// for every item, and nothing is signed without the person's explicit click.
import type { SignOffEligibilityOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { BULK_F, SHL12, STALE_ELIGIBILITY } from "../../fixtures/seed/review";
import { renderRoutes } from "../../testing/support";
import { BulkSignOffSheet, SignOffSheet } from ".";
import { BULK, OPENS, type Shl12State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

const ROLE: Record<SignOffEligibilityOut["level"], string> = {
  L1_preparer: "Preparer",
  L2_reviewer: "Reviewer",
  L3_manager: "Manager",
  L4_partner: "Partner",
  L5_eqr: "EQR (L5)",
};

function writes(calls: { method: string }[]): number {
  return calls.filter((c) => c.method !== "GET").length;
}

function open(state: Shl12State, bulk = false): { method: string; path: string; body: unknown }[] {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const o = OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () =>
        bulk ? (
          <BulkSignOffSheet
            targets={BULK}
            level="L2_reviewer"
            open
            onOpenChange={() => undefined}
          />
        ) : (
          <SignOffSheet
            target={{ type: o.type, id: o.id }}
            level={o.level}
            open
            onOpenChange={() => undefined}
          />
        ),
    },
  ]);
  return calls;
}

describe("P-04-T51: the level picker never offers a denied level", () => {
  const frames: [Shl12State, SignOffEligibilityOut][] = [
    ["a", SHL12.a],
    ["g", SHL12.g],
  ];
  for (const [state, eligibility] of frames) {
    it(`${state}: exactly the levels the server allows`, async () => {
      open(state);
      const picker = await screen.findByRole("tablist", { name: "Sign-off level" });
      const offered = within(picker)
        .getAllByRole("tab")
        .map((t) => t.textContent);
      expect(offered).toEqual(eligibility.levels_allowed.map((l) => ROLE[l]));
      const denied = (Object.keys(ROLE) as SignOffEligibilityOut["level"][]).filter(
        (l) => !eligibility.levels_allowed.includes(l),
      );
      for (const l of denied) expect(offered).not.toContain(ROLE[l]);
    });
  }
});

describe("P-04-T51: blocked states are stated in words and send nothing", () => {
  for (const state of ["b", "c", "d", "h"] as const) {
    it(`${state}: the CTA is disabled and described by the failing check's words`, async () => {
      const calls = open(state);
      await screen.findByRole("tablist", { name: "Sign-off level" });
      const ctas = screen
        .getAllByRole<HTMLButtonElement>("button")
        .filter(
          (b) => b.closest("[data-signoff='footer']") !== null && b.textContent !== "Cancel",
        );
      expect(ctas).toHaveLength(1);
      const cta = ctas[0] as HTMLButtonElement;
      expect(cta.disabled).toBe(true);
      const described = document.getElementById(cta.getAttribute("aria-describedby") ?? "");
      expect((described?.textContent ?? "").trim().length).toBeGreaterThan(0);
      fireEvent.click(cta);
      expect(writes(calls)).toBe(0);
    });
  }
});

describe("P-04-T51: a stale sign-off offers only Re-sign", () => {
  it("e: Re-sign is the only signing control; nothing keeps the old sign-off", async () => {
    expect(STALE_ELIGIBILITY.ladder.find((l) => l.level === "L2_reviewer")?.latest?.stale).toBe(
      true,
    );
    open("e");
    const resign = await screen.findByRole("button", { name: /^Re-sign as Reviewer \(L2\)/u });
    expect(resign).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Sign off as/u })).toBeNull();
    expect(
      screen.queryByRole("button", { name: /keep|still valid|confirm unchanged/iu }),
    ).toBeNull();
    expect(screen.getAllByText("Changed after sign-off").length).toBeGreaterThan(0);
  });
});

describe("P-04-T51: no sign-off without the explicit click", () => {
  it("a: opening, choosing and reading send nothing; one click sends one sign-off", async () => {
    const calls = open("a");
    const cta = await screen.findByRole("button", { name: /^Sign off as Reviewer \(L2\)/u });
    expect(writes(calls)).toBe(0);
    fireEvent.click(cta);
    await waitFor(() => {
      expect(writes(calls)).toBe(1);
    });
  });
});

describe("P-04-T51: bulk per-item results", () => {
  it("f: every item comes back signed or excluded, with words", async () => {
    open("f", true);
    fireEvent.click(
      await screen.findByRole("button", { name: /^Sign off 3 as Reviewer \(L2\)/u }),
    );
    await waitFor(() => {
      expect(document.querySelectorAll("[data-bulk-result]")).toHaveLength(BULK_F.results.length);
    });
    for (const r of document.querySelectorAll("[data-bulk-result]")) {
      expect(r.textContent.trim().length).toBeGreaterThan(0);
    }
    expect(document.querySelectorAll('[data-bulk-result="signed"]')).toHaveLength(BULK_F.signed);
    expect(document.querySelectorAll('[data-bulk-result="excluded"]')).toHaveLength(
      BULK_F.excluded,
    );
  });
});
