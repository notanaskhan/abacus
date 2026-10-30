// SHL-12 · Sign-off modal (P-04-T48). One test per frame built (a, a′, b, c, d, e, g, h) on its
// fixture scenario, and the acceptance: "Each blocked frame names its reason in words, a-prime
// shows the MD and HL ticks, and h keeps Resolve 11 issues to approve disabled." Tier C (pixels) is
// the visual suite's; here the content, the gate and the write the person's click sends.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { HASH, TB } from "../../fixtures/seed/review";
import { renderRoutes } from "../../testing/support";
import { SignOffChips, SignOffSheet } from ".";
import { OPENS, STATES, type Shl12State, scenarios } from "./scenarios";

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

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function show(state: Shl12State, extra: Record<string, FixtureHandler> = {}): Call[] {
  const calls: Call[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...extra }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const open = OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <SignOffSheet
          target={{ type: open.type, id: open.id }}
          level={open.level}
          meta={open.meta}
          open
          onOpenChange={() => undefined}
        />
      ),
    },
  ]);
  return calls;
}

const cta = (name: RegExp) => screen.findByRole<HTMLButtonElement>("button", { name });

/** A blocked frame: the CTA is disabled and described by the failing check's words. */
async function blockedBy(name: RegExp, words: string): Promise<void> {
  const button = await cta(name);
  expect(button.disabled).toBe(true);
  const described = button.getAttribute("aria-describedby");
  expect(described).toBeTruthy();
  expect(document.getElementById(described ?? "")?.textContent).toContain(words);
}

describe("SHL-12", () => {
  it("builds a, a′, b, c, d, e, g and h (f is P-04-T49's)", () => {
    expect(STATES).toEqual(["a", "ap", "b", "c", "d", "e", "g", "h"]);
  });

  it("a: workpaper card, levels the matrix allows, the ladder with the adoption line, checks, statement", async () => {
    show("a");
    expect(await screen.findByText("Trial Balance")).toBeTruthy();
    expect(
      screen.getByText("Northwind Robotics 401(k) Plan · PY2025 · Version 1", { exact: false }),
    ).toBeTruthy();
    expect(
      screen.getByText(/Content hash sha256:9f4c…e21a · 14 cells · 3 citations/u),
    ).toBeTruthy();
    const picker = screen.getByRole("tablist", { name: "Sign-off level" });
    expect(picker.textContent).toContain("Reviewer");
    expect(picker.textContent).not.toContain("EQR");
    expect(
      screen.getByText(
        "Performed by Agent run #4127 under the direction of Marcus Delaney · adopted by MD",
      ),
    ).toBeTruthy();
    expect(screen.getByText(/You · now/u)).toBeTruthy();
    expect(screen.getByText(/Optional for this workpaper/u)).toBeTruthy();
    expect(screen.getByText(/Thomas Whitcombe · at completion/u)).toBeTruthy();
    expect(screen.getByText("Open review notes: 0")).toBeTruthy();
    expect(
      screen.getByText("Independence confirmed for Northwind · Hannah Leclerc · Aug 3, 2026"),
    ).toBeTruthy();
    expect(
      screen.getByText("You did not prepare this workpaper (preparer: Marcus Delaney)"),
    ).toBeTruthy();
    expect(screen.getByText("Every value cited · 14 of 14 cells")).toBeTruthy();
    expect(screen.getByText(/Planning not approved \(Gate G4\)/u)).toBeTruthy();
    expect(
      screen.getByText(
        "I reviewed this work. It is sufficient and appropriate, and its conclusions are supported.",
      ),
    ).toBeTruthy();
    const sign = await cta(/^Sign off as Reviewer \(L2\)$/u);
    expect(sign.disabled).toBe(false);
    expect(sign.getAttribute("data-human-verb")).toBe("Sign off");
  });

  it("a → a′: signing sends the hash and statement seen, waits for the server, then toasts", async () => {
    const calls = show("a", { ...scenarios.ap.handlers });
    fireEvent.click(await cta(/^Sign off as Reviewer \(L2\)$/u));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path === "/v1/sign-offs")).toBe(true);
    });
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      target_type: "workpaper",
      target_id: TB,
      level: "L2_reviewer",
      kind: "ladder",
      seen_hash: HASH,
      statement_version: "bh-review-v1",
    });
    await waitFor(() => {
      expect(
        toastStore.list().some((t) => t.text === "Signed off Trial Balance (L2) · 9:41 AM"),
      ).toBe(true);
    });
  });

  it("a′: the header shows the MD and HL ticks", async () => {
    restore = installFixtureMode(scenarios.ap);
    renderRoutes([
      { path: "/", component: () => <SignOffChips target={{ type: "workpaper", id: TB }} /> },
    ]);
    await waitFor(() => {
      expect(document.querySelector("[data-sign-off-chip='MD']")).not.toBeNull();
    });
    expect(document.querySelector("[data-sign-off-chip='HL']")).not.toBeNull();
  });

  it("b: two open notes block L2 and the CTA says to clear them", async () => {
    show("b");
    expect(await screen.findByText("2 open review notes")).toBeTruthy();
    await blockedBy(/^Clear 2 open notes to sign off$/u, "2 open review notes");
  });

  it("c: the preparer cannot review their own workpaper", async () => {
    show("c");
    await blockedBy(
      /^Sign off as Reviewer \(L2\)$/u,
      "You prepared this workpaper. A different reviewer must sign L2.",
    );
  });

  it("d: no independence confirmation on file (Gate G2)", async () => {
    show("d");
    await blockedBy(
      /^Sign off as Reviewer \(L2\)$/u,
      "Your independence confirmation for Northwind is not on file (Gate G2)",
    );
    expect(screen.getByText(/Confirm independence…/u)).toBeTruthy();
  });

  it("e: the stale L2 chip is struck, View changes, and only Re-sign", async () => {
    show("e");
    const re = await cta(/^Re-sign as Reviewer \(L2\)$/u);
    expect(re.disabled).toBe(false);
    expect(re.getAttribute("data-human-verb")).toBe("Sign off");
    expect(document.querySelector("[data-sign-off-chip='HL'][data-stale]")).not.toBeNull();
    expect(screen.getByText("Changed after sign-off")).toBeTruthy();
    expect(screen.getByText(/View changes/u)).toBeTruthy();
  });

  it("g: the EQR sees one option and the EQR statement", async () => {
    show("g");
    const picker = await screen.findByRole("tablist", { name: "Sign-off level" });
    expect(picker.querySelectorAll("[role='tab']")).toHaveLength(1);
    expect(picker.textContent).toContain("EQR (L5)");
    expect(screen.getByText("As EQR you can't sign L1–L4 on this engagement")).toBeTruthy();
    expect(
      screen.getByText(
        "I objectively evaluated the significant judgments and the conclusions reached.",
      ),
    ).toBeTruthy();
  });

  it("h: final approval is blocked by 11 open issues and stays disabled", async () => {
    const calls = show("h");
    expect(await screen.findByText("2025 Form 1065")).toBeTruthy();
    expect(screen.getByText("Partner · final approval (BH-TAX-02)")).toBeTruthy();
    expect(
      screen.getByText("11 issues open (5 waiting on the client · 6 review points)"),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Tax-exempt interest 6,200 omitted from the capital rollforward (M-2 off 6,200)",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "You did not prepare or review this return (preparer: Olivia Brandt · reviewer: Samuel Ito)",
      ),
    ).toBeTruthy();
    const approve = await blockedByReturn();
    fireEvent.click(approve);
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("no agent ever gets the sign-off control (INV-1)", async () => {
    show("a");
    await cta(/^Sign off as Reviewer \(L2\)$/u);
    expect(document.querySelector("[data-actor='agent'] [data-human-verb]")).toBeNull();
  });
});

async function blockedByReturn(): Promise<HTMLButtonElement> {
  await blockedBy(/^Resolve 11 issues to approve$/u, "11 issues open");
  const button = await cta(/^Resolve 11 issues to approve$/u);
  expect(button.getAttribute("data-human-verb")).toBe("Approve");
  return button;
}
