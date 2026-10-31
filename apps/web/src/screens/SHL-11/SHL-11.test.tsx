// SHL-11 · Decision card (P-04-T50, T52): one test per frame (a to h; e in InlineCard.test.tsx) on its fixture
// scenario, and the acceptance: "SHL-11a and c match their artboards at Tier C, and Hannah
// Leclerc's frame b offers no Decide." Tier C (pixels) is the visual suite's; here the content,
// the reserved-person rule and the write the person's click sends.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { DecisionSheet } from ".";
import { CARD_ID, STATES, type Shl11State, scenarios } from "./scenarios";

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

function show(state: Shl11State, extra: Record<string, FixtureHandler> = {}): Call[] {
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
  renderRoutes([
    {
      path: "/",
      component: () => <DecisionSheet cardId={CARD_ID} open onOpenChange={() => undefined} />,
    },
  ]);
  return calls;
}

const question = "Which planning materiality should the Northwind PY2025 audit use?";

describe("SHL-11", () => {
  it("builds every frame, a to h (e is the inline card, P-04-T52)", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "h"]);
  });

  it("a: the question, reserved line, options with the agent's tag, factors; Decide waits", async () => {
    // c's answer to the decide write (a's board names the request, c draws the decided card).
    const decided = Object.fromEntries(
      Object.entries(scenarios.c.handlers).filter(([route]) => route.startsWith("POST ")),
    );
    const calls = show("a", decided);
    expect(await screen.findByText(question)).toBeTruthy();
    expect(
      screen.getByText(
        /Reserved to Engagement Partner · Margaret Okonkwo · blocking 3 workpapers/u,
      ),
    ).toBeTruthy();
    expect(screen.getByText("Recommended by Accrued Agent")).toBeTruthy();
    expect(screen.getByText("0.5% – 2.0% of net assets (BH EBP v3 §4.2)")).toBeTruthy();
    expect(screen.getByRole("group", { name: "Qualitative factors" })).toBeTruthy();
    // The session (the signed-in person) loads before the HumanAction draws.
    const decide = await screen.findByRole<HTMLButtonElement>(
      "button",
      { name: /^Decide/u },
      { timeout: 10_000 },
    );
    expect(decide.disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: "1.5% — $252,200" }));
    expect(decide.disabled).toBe(true); // a rationale is required
    fireEvent.change(screen.getByLabelText("Rationale (required)"), {
      target: {
        value:
          "Recurring engagement, stable plan, no prior misstatements above CT. 1.5% of net assets, consistent with PY2024.",
      },
    });
    expect(decide.disabled).toBe(false);
    fireEvent.click(decide);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/decide"))).toBe(true);
    });
    const body = calls.find((c) => c.path.endsWith("/decide"))?.body as {
      option_key: string;
      factors: string[];
      seen_version: number;
    };
    expect(body.option_key).toBe("pct_1_5");
    expect(body.factors).toEqual(["late_deposits", "users"]);
    expect(body.seen_version).toBe(1);
  });

  it("b: Hannah Leclerc waits on Margaret: radios disabled, Notify, no Decide", async () => {
    show("b");
    expect(await screen.findByText(/Waiting on Margaret Okonkwo · requested/u)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Decide/u })).toBeNull();
    for (const radio of screen.getAllByRole<HTMLInputElement>("radio")) {
      expect(radio.disabled || radio.getAttribute("aria-disabled") === "true").toBe(true);
    }
    expect(screen.getByRole("button", { name: "Notify Margaret" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Request more analysis/u })).toBeTruthy();
    expect(screen.queryByLabelText("Rationale (required)")).toBeNull();
  });

  it("c: decided, the line with the figures and the rationale as text", async () => {
    show("c");
    expect(await screen.findByText("Decided")).toBeTruthy();
    const line = document.querySelector("[data-decision-line]");
    expect(line?.textContent).toContain("Margaret Okonkwo");
    expect(line?.textContent).toContain("v2: 1.5% = $252,200 · PM $189,150 · CT $12,610");
    expect(screen.getByRole("button", { name: "View history" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Decide/u })).toBeNull();
  });

  it("d: the history after the reassessment reads v1, v2, v3 with no change", async () => {
    show("d");
    await screen.findByText(question);
    const rows = [...document.querySelectorAll("[data-history]")].map((r) => r.textContent);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toContain("v1 · proposed by Accrued Agent");
    expect(rows[1]).toContain("v2 · decided by MO");
    expect(rows[2]).toContain(
      "v3 · reassessed at final on $16,861,000: 1.5% = $252,900 — difference $700, no change",
    );
  });

  it("f: deficiency severity with Significant deficiency recommended", async () => {
    show("f");
    expect(
      await screen.findByText("How severe is the deficiency in contribution-remittance controls?"),
    ).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Material weakness" })).toBeTruthy();
  });

  it("g: §754 says the election is Ridgeline's", async () => {
    show("g");
    expect(
      await screen.findByText(
        "Should we recommend that Ridgeline make a §754 election for TY2025?",
      ),
    ).toBeTruthy();
    expect(screen.getByText(/The election is Ridgeline's to make/u)).toBeTruthy();
    expect(screen.getByText(/Reserved to Tax Partner · Daniel Reyes/u)).toBeTruthy();
  });

  it("h: superseded by v3, values struck", async () => {
    show("h");
    expect(await screen.findByText("Superseded by v3")).toBeTruthy();
    expect(document.querySelector("[data-decision-line]")?.className).toContain("line-through");
  });
});
