// A-04-T21 (TASK-3027): AUD-05 a–e in fixture mode. Row acceptance: "AUD-05 a-e render at Tier C,
// Approve minutes is absent for Marcus, and Escalate opens SHL-14 prefilled without sending
// anything." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { PBC_FLAG, RISK_PAPER } from "../../fixtures/seed/aud05";
import { newQueryClient } from "../../testing/support";
import { NarrativePage, type NarrativeTab } from "./Narrative";
import { type Aud05State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const sent: string[] = [];

function show(
  state: Aud05State,
  tab: NarrativeTab = "risk",
  onEscalate = vi.fn(),
): { onEscalate: ReturnType<typeof vi.fn> } {
  const scenario = scenarios[state];
  restore = installFixtureMode({
    ...scenario,
    get handlers() {
      return {
        ...scenario.handlers,
        "POST /v1/engagements/{engagement_id}/workpapers/{workpaper_id}/flags/{flag_id}/convert":
          () => {
            sent.push("convert");
            return new Response("{}", { status: 500 });
          },
      };
    },
  });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <NarrativePage
        auditId={NORTHWIND_AUDIT}
        workpaperId={RISK_PAPER}
        tab={tab}
        onTab={() => undefined}
        onRegister={() => undefined}
        onEscalate={onEscalate}
        onAdopt={() => undefined}
      />
    </QueryClientProvider>,
  );
  return { onEscalate };
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

describe("AUD-05", () => {
  it("a: the two menus, the PBC GAP note and Citations (9)", async () => {
    show("a");
    await drawn("[data-section='menu_2']");
    expect(document.body.textContent).toContain("MENU 1 — UNDERSTANDING THE PLAN");
    expect(document.body.textContent).toContain("MENU 2 — OVERALL RISKS AND FRAUD");
    const flag = await drawn(`[data-flag='${PBC_FLAG}']`);
    expect(flag.textContent).toContain("PBC GAP — the trust agreement");
    expect(document.body.textContent).toContain("Citations (9)");
    expect(document.body.textContent).not.toContain("scope limitation");
  });

  it("b: Marcus sees the minutes awaiting EP approval and no Approve minutes", async () => {
    show("b", "fraud");
    const minutes = await drawn("[data-aud05='minutes']");
    expect(minutes.textContent).toContain("Awaiting EP approval");
    expect(document.body.textContent).not.toContain("Approve minutes");
    const excluded = await drawn("[data-aud05='excluded']");
    expect(excluded.textContent).toBe(
      "Thomas Whitcombe (EQR) is not invited, to keep the review objective.",
    );
  });

  it("b: Margaret, the EP, sees Approve minutes", async () => {
    show("b_partner", "fraud");
    await waitFor(() => {
      expect(
        [...document.querySelectorAll("button")].some((b) => b.textContent === "Approve minutes"),
      ).toBe(true);
    });
  });

  it("c: Escalate… hands the flag to SHL-14 and sends nothing", async () => {
    const { onEscalate } = show("c");
    const button = await drawn(`[data-escalate='${PBC_FLAG}']`);
    fireEvent.click(button);
    expect(onEscalate).toHaveBeenCalledWith(expect.objectContaining({ id: PBC_FLAG }));
    expect(sent).toEqual([]);
  });

  it("c: Remind… drafts a follow-up, sends nothing, and the flag stays open", async () => {
    show("c");
    fireEvent.click(await drawn(`[data-remind='${PBC_FLAG}']`));
    const status = await drawn("[data-aud05='remind-status']");
    expect(status.textContent).toBe(
      "Follow-up drafted. Nothing has been sent: a person sends it.",
    );
    expect(document.querySelector(`[data-escalate='${PBC_FLAG}']`)).not.toBeNull();
  });

  it("c: Remind… with nothing open to chase points to Escalate…", async () => {
    const scenario = scenarios.c;
    restore = installFixtureMode({
      ...scenario,
      get handlers() {
        return {
          ...scenario.handlers,
          "POST /v1/engagements/{engagement_id}/workpapers/{workpaper_id}/flags/{flag_id}/remind":
            () =>
              new Response(JSON.stringify({ detail: "nothing_to_remind" }), {
                status: 409,
                headers: { "content-type": "application/json" },
              }),
        };
      },
    });
    render(
      <QueryClientProvider client={newQueryClient()}>
        <NarrativePage
          auditId={NORTHWIND_AUDIT}
          workpaperId={RISK_PAPER}
          tab="risk"
          onTab={() => undefined}
          onRegister={() => undefined}
          onEscalate={() => undefined}
          onAdopt={() => undefined}
        />
      </QueryClientProvider>,
    );
    fireEvent.click(await drawn(`[data-remind='${PBC_FLAG}']`));
    const status = await drawn("[data-aud05='remind-status']");
    expect(status.textContent).toBe("No open request to chase. Escalate… drafts one.");
  });

  it("d: Hannah's L2 reads Reviewed · HL and the note keeps its place", async () => {
    show("d");
    const pill = await drawn("[data-reviewed]");
    expect(pill.textContent).toBe("Reviewed · HL");
    expect(document.querySelector(`[data-flag='${PBC_FLAG}']`)).not.toBeNull();
  });

  it("e: the agent's draft shows Agent draft and Adopt draft", async () => {
    show("e");
    await drawn("[data-row='management_override'][data-state='suggested']");
    expect(document.body.textContent).toContain("Agent draft");
    expect(document.body.textContent).toContain("Adopt draft");
  });
});
