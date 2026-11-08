// A-04-T20 (TASK-3026): AUD-08 a, b, b2 and d in fixture mode. Row acceptance: "AUD-08 a, b, b2
// and d render at Tier C, the Unaddressed tally filters to R8, and only Margaret sees the approve
// controls." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { toast } from "@abacus/ui";
import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { R3_CARD, aud08Drawer, aud08Register } from "../../fixtures/seed/aud08";
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

function drawer(
  state: Aud08State,
  onDecide = vi.fn(),
  onNotify: (path: string) => void = () => undefined,
): void {
  const scenario = scenarios[state];
  restore = installFixtureMode({
    ...scenario,
    handlers: {
      ...scenario.handlers,
      "POST /v1/decision-cards/{card_id}/notify": (request) => {
        onNotify(request.path);
        return json({
          card_id: R3_CARD,
          notified_user_id: "00000000-0000-4000-8000-000000000002",
          notified_at: "2026-09-14T14:30:00-05:00",
        });
      },
    },
  });
  const variant = state === "b2" ? "b2" : "a";
  const r3 = aud08Register(variant).risks[2];
  if (r3 === undefined) throw new Error("R3");
  render(
    <QueryClientProvider client={newQueryClient()}>
      <RiskDrawer
        engagementId="00000000-0000-4000-8000-000000000001"
        risk={r3}
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

  it("b: Remind calls C3's notify on the pending card and confirms in words (DEC-2420)", async () => {
    const notified: string[] = [];
    const shown = vi.spyOn(toast, "show");
    drawer("b", vi.fn(), (path) => notified.push(path));
    const footer = await drawn("[data-aud08='routed-footer']");
    fireEvent.click(within(footer).getByRole("button", { name: "Remind Margaret…" }));
    await waitFor(() => {
      expect(notified).toEqual([`/v1/decision-cards/${R3_CARD}/notify`]);
    });
    await waitFor(() => {
      expect(shown).toHaveBeenCalledWith({ kind: "success", text: "Reminded Margaret Okonkwo." });
    });
    shown.mockRestore();
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

// A-04-T26 (TASK-3221): AUD-08 c, e, f and g. Row acceptance: "AUD-08 c, e, f and g render at Tier
// C, nothing auto-adopts, and with workpapers.drafting off every agent control is absent and Check
// coverage shows the code result."
describe("AUD-08 c, e, f, g (A-04-T26)", () => {
  it("c: the Linkage tab shows dots and R8 Suggested", async () => {
    show("c");
    const tab = await waitFor(() => {
      const found = document.querySelector<HTMLElement>(
        '[role="tab"]:nth-child(5), button[aria-label="Linkage"]',
      );
      const byText = Array.from(document.querySelectorAll<HTMLElement>('[role="tab"]')).find(
        (t) => t.textContent === "Linkage",
      );
      const el = byText ?? found;
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    fireEvent.click(tab);
    const matrix = await waitFor(() => {
      const el = document.querySelector('[data-aud08="linkage"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    expect(matrix.querySelector('[data-risk="R8"]')?.textContent).toContain("Suggested");
    expect(matrix.querySelectorAll('[data-dot="linked"]').length).toBeGreaterThan(0);
  });

  it("g: Identify risks with agent shows code's coverage and Open R8", async () => {
    show("g");
    const button = await waitFor(() => {
      const el = Array.from(document.querySelectorAll("button")).find(
        (b) => b.textContent === "Identify risks with agent",
      );
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    fireEvent.click(button);
    const result = await waitFor(() => {
      const el = document.querySelector('[data-aud08="identify-result"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    expect(result.textContent).toContain("(10 of 10)");
    expect(result.textContent).toContain("Open R8 →");
  });

  it("drafting off: no agent control, Check coverage shows the code result", async () => {
    show("drafting_off");
    const check = await waitFor(() => {
      const el = Array.from(document.querySelectorAll("button")).find(
        (b) => b.textContent === "Check coverage",
      );
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    expect(document.body.textContent).not.toContain("Identify risks with agent");
    fireEvent.click(check);
    const result = await waitFor(() => {
      const el = document.querySelector('[data-aud08="identify-result"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    expect(result.textContent).not.toContain("I compared");
  });

  it("f: a drafted rationale is ink-2 with Adopt · Edit · Discard and nothing auto-adopts", async () => {
    restore = installFixtureMode(scenarios.f);
    const r8 = aud08Register("a").risks[7];
    if (r8 === undefined) throw new Error("R8");
    render(
      <QueryClientProvider client={newQueryClient()}>
        <RiskDrawer
          engagementId={NORTHWIND_AUDIT}
          risk={r8}
          onClose={() => undefined}
          onDecide={vi.fn()}
        />
      </QueryClientProvider>,
    );
    const footer = await waitFor(() => {
      const el = document.querySelector('[data-aud08="drafted-footer"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    expect(footer.textContent).toContain("Adopt");
    expect(document.querySelector("[data-drafted]")).toBeTruthy();
    // The proposed wording is on show, and it is the suggestion's, not the row's (DEC-2481).
    const proposed = document.querySelector('[data-aud08="proposed-rationale"]');
    expect(proposed?.textContent).toContain("QACA escalation");
  });

  it("b: an adopted rationale is the person's: no marker and no Adopt", async () => {
    restore = installFixtureMode(scenarios.b);
    const r3 = aud08Register("a").risks[2];
    if (r3 === undefined) throw new Error("R3");
    render(
      <QueryClientProvider client={newQueryClient()}>
        <RiskDrawer
          engagementId={NORTHWIND_AUDIT}
          risk={r3}
          cardId={null}
          onClose={() => undefined}
          onDecide={vi.fn()}
        />
      </QueryClientProvider>,
    );
    const card = await waitFor(() => {
      const el = document.querySelector('[data-aud08="rationale"]');
      expect(el?.textContent).toContain("9 business days later");
      return el as HTMLElement;
    });
    expect(card.querySelector("[data-drafted]")).toBeNull();
    expect(card.querySelector('[data-aud08="drafted-footer"]')).toBeNull();
    expect(card.querySelector('[data-aud08="proposed-rationale"]')).toBeNull();
  });

  it("a re-draft keeps the adopted wording in view, and Adopt carries the suggestion's version", async () => {
    const seen: unknown[] = [];
    const b = scenarios.b;
    restore = installFixtureMode({
      ...b,
      handlers: {
        ...b.handlers,
        "GET /v1/engagements/{engagement_id}/risks/{risk_id}": () =>
          new Response(
            JSON.stringify({
              ...aud08Drawer("a"),
              rationale_suggestion: {
                suggestion_id: "11111111-1111-4111-8111-111111111111",
                text: "A re-drafted rationale",
                citations: 2,
                version: 4,
              },
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          ),
        "POST /v1/suggestions/{suggestion_id}/adopt": (request) => {
          seen.push(request.body);
          return json({});
        },
      },
    });
    const r3 = aud08Register("a").risks[2];
    if (r3 === undefined) throw new Error("R3");
    render(
      <QueryClientProvider client={newQueryClient()}>
        <RiskDrawer
          engagementId={NORTHWIND_AUDIT}
          risk={r3}
          cardId={null}
          onClose={() => undefined}
          onDecide={vi.fn()}
        />
      </QueryClientProvider>,
    );
    const proposed = await waitFor(() => {
      const el = document.querySelector('[data-aud08="proposed-rationale"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    expect(proposed.textContent).toContain("A re-drafted rationale");
    expect(document.querySelector('[data-aud08="rationale"]')?.textContent).toContain(
      "9 business days later",
    );
    const adopt = document.querySelector('[data-aud08="drafted-footer"] button');
    fireEvent.click(adopt as HTMLButtonElement);
    await waitFor(() => {
      expect(seen).toEqual([{ seen_version: 4 }]);
    });
  });

  it("f: the drafted response stays pending: EBP-03 with Adopt · Edit · Discard, nothing linked", async () => {
    restore = installFixtureMode(scenarios.f);
    const r8 = aud08Register("a").risks[7];
    if (r8 === undefined) throw new Error("R8");
    render(
      <QueryClientProvider client={newQueryClient()}>
        <RiskDrawer
          engagementId={NORTHWIND_AUDIT}
          risk={r8}
          cardId={null}
          onClose={() => undefined}
          onDecide={vi.fn()}
        />
      </QueryClientProvider>,
    );
    const card = await waitFor(() => {
      const el = document.querySelector('[data-aud08="response"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    expect(card.textContent).toContain("EBP-03");
    expect(card.querySelector('[data-aud08="drafted-footer"]')?.textContent).toContain("Adopt");
    expect(card.querySelector("[data-drafted]")).toBeTruthy();
  });

  // ED-323 (Q-03-T173): Edit once adopted the suggestion with the model's own rationale as the
  // person's edit (ADR-065). It now hands off to the host's editor and adopts nothing.
  it("f: Edit opens the host's editor and never adopts the model's text", async () => {
    const adopts: string[] = [];
    const f = scenarios.f;
    restore = installFixtureMode({
      ...f,
      handlers: {
        ...f.handlers,
        "POST /v1/suggestions/{suggestion_id}/adopt": (request) => {
          adopts.push(request.path);
          return new Response("{}", {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        },
      },
    });
    const r8 = aud08Register("a").risks[7];
    if (r8 === undefined) throw new Error("R8");
    const onEdit = vi.fn();
    render(
      <QueryClientProvider client={newQueryClient()}>
        <RiskDrawer
          engagementId={NORTHWIND_AUDIT}
          risk={r8}
          onClose={() => undefined}
          onDecide={vi.fn()}
          onEdit={onEdit}
        />
      </QueryClientProvider>,
    );
    const footer = await waitFor(() => {
      const el = document.querySelector('[data-aud08="drafted-footer"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    const edit = [...footer.querySelectorAll("button")].find((b) => b.textContent === "Edit");
    if (edit === undefined) throw new Error("no Edit");
    fireEvent.click(edit);
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(adopts).toEqual([]);
  });
});
