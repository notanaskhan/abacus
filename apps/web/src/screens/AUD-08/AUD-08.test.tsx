// A-04-T20 (TASK-3026): AUD-08 a, b, b2 and d in fixture mode. Row acceptance: "AUD-08 a, b, b2
// and d render at Tier C, the Unaddressed tally filters to R8, and only Margaret sees the approve
// controls." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { aud08Register } from "../../fixtures/seed/aud08";
import { newQueryClient } from "../../testing/support";
import { RiskRegisterPage } from "./Register";
import { RiskDrawer } from "./RiskDrawer";
import { type Aud08State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function Page(): JSX.Element {
  const [filter, setFilter] = useState<"unaddressed" | null>(null);
  return (
    <RiskRegisterPage
      auditId={NORTHWIND_AUDIT}
      filter={filter}
      onFilter={setFilter}
      onRisk={() => undefined}
    />
  );
}

function show(state: Aud08State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Page />
    </QueryClientProvider>,
  );
}

function drawer(state: Aud08State, onDecide = vi.fn()): void {
  restore = installFixtureMode(scenarios[state]);
  const variant = state === "b2" ? "b2" : "a";
  const r3 = aud08Register(variant).risks[2];
  if (r3 === undefined) throw new Error("R3");
  render(
    <QueryClientProvider client={newQueryClient()}>
      <RiskDrawer
        engagementId="00000000-0000-4000-8000-000000000001"
        risk={r3}
        cardId={aud08Register(variant).approved_card_id ?? null}
        onClose={() => undefined}
        onDecide={onDecide}
      />
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

describe("AUD-08", () => {
  it("a: ten risks and the server's tally (10 · 2 + 1 proposed · 2 · 3 · 1 · Pending)", async () => {
    show("a");
    const tally = await drawn("[data-aud08='tally']");
    expect(tally.textContent).toContain("1 proposed");
    expect(tally.textContent).toContain("Pending");
    expect(document.querySelectorAll("[data-risk]").length).toBe(10);
    const r3 = await drawn("[data-risk='R3']");
    expect(r3.textContent).toContain("BH-EBP-410 step 6 → EBP-04 Remittance timeliness");
    expect(document.querySelector("[data-risk='R8']")?.textContent).toContain("Unaddressed risk");
    expect(document.body.textContent).not.toContain("$");
  });

  it("the UNADDRESSED card filters the grid to R8", async () => {
    show("a");
    const card = await drawn("[data-tally='unaddressed']");
    fireEvent.click(card);
    await waitFor(() => {
      const shown = [...document.querySelectorAll<HTMLElement>("[data-risk]")].map(
        (r) => r.dataset.risk,
      );
      expect(shown).toEqual(["R8"]);
    });
  });

  it("d: EP approved on every row, Approved in the tally", async () => {
    show("d");
    const tally = await drawn("[data-aud08='tally']");
    expect(tally.textContent).toContain("Approved");
    expect(tally.textContent).not.toContain("proposed");
    await waitFor(() => {
      const rows = [...document.querySelectorAll("[data-risk]")];
      expect(rows.length).toBe(10);
      expect(rows.every((r) => r.textContent.includes("EP approved"))).toBe(true);
    });
  });

  it("b: Hannah's drawer reads Routed to Margaret Okonkwo with Remind, no approve controls", async () => {
    drawer("b");
    const footer = await drawn("[data-aud08='routed-footer']");
    expect(footer.textContent).toContain("Routed to Margaret Okonkwo");
    expect(footer.textContent).toContain("Remind Margaret…");
    expect(document.body.textContent).not.toContain("Approve as significant risk");
    const rationale = await drawn("[data-aud08='rationale']");
    expect(rationale.textContent).toContain("9 business days later");
  });

  it("b2: only Margaret sees Approve as significant risk; it opens SHL-11 with R3", async () => {
    const onDecide = vi.fn();
    drawer("b2", onDecide);
    const footer = await drawn("[data-aud08='partner-footer']");
    const approve = [...footer.querySelectorAll("button")].find(
      (b) => b.textContent === "Approve as significant risk",
    );
    expect(approve).toBeDefined();
    fireEvent.click(approve as HTMLButtonElement);
    expect(onDecide).toHaveBeenCalledWith(expect.any(String), "R3");
  });
});
