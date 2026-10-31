// HOME-02 · the detail pane per gate class (I-01-T17). Acceptance: "States a to d and g render from
// data, every verb is a HumanAction that opens its overlay, and no control appears on an
// agent-owned element." Plus DV-1 (Decide waits for an option and a rationale, AC7.1) and the
// generic fallback for an unknown subkind (AC7.8).
import type { HumanGateOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { humanGateHandlers } from "../../fixtures/handlers/human-gates";
import { getSeed } from "../../fixtures/seed";
import { DECISION_754, FELD_PROPOSAL, M2_FIX } from "../../fixtures/seed/approvals-detail";
import "../../routes/firm/sheets"; // registers the `?ov=` keys the detail opens
import { newQueryClient } from "../../testing/support";
import { HOME02 } from ".";
import { type Home02State, freshScenarios, selectedGate } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

interface Seen {
  posts: { path: string; body: unknown }[];
  search: () => Record<string, unknown>;
}

function show(
  state: Home02State,
  extra: Record<string, FixtureHandler> = {},
  gate: string | null = selectedGate(state),
): Seen {
  const posts: Seen["posts"] = [];
  const scenario = freshScenarios()[state]; // Decide writes into its handlers
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...extra }).map(([key, handler]) => [
      key,
      ((request) => {
        if (key.startsWith("POST ")) posts.push({ path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const root = createRootRoute({ component: Outlet });
  const router = createRouter({
    routeTree: root.addChildren([
      createRoute({
        getParentRoute: () => root,
        path: "/",
        component: () => <HOME02 gate={gate} />,
      }),
    ]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { posts, search: () => router.state.location.search as Record<string, unknown> };
}

async function detail(kind: string): Promise<HTMLElement> {
  return waitFor(() => {
    const found = document.querySelector<HTMLElement>(`[data-home02-detail="${kind}"]`);
    if (found === null) throw new Error(`no ${kind} detail yet`);
    return found;
  });
}

function footer(): HTMLElement {
  const found = document.querySelector<HTMLElement>('[data-home02="footer"]');
  if (found === null) throw new Error("no footer");
  return found;
}

/** Every button in the detail and footer that names a gate verb is a HumanAction. */
function verbsAreHumanActions(): void {
  const panes = [
    ...document.querySelectorAll<HTMLElement>("[data-home02-detail], [data-home02='footer']"),
  ];
  for (const pane of panes) {
    for (const b of within(pane).queryAllByRole("button")) {
      if (/^(✓ )?(Decide|Approve|Sign off|Send|Release|Post)/u.test(b.textContent.trim())) {
        expect(b.getAttribute("data-human-verb")).not.toBeNull();
      }
    }
  }
}

/** INV-1: nothing the agent owns carries a control. */
function noControlOnAgent(): void {
  for (const el of document.querySelectorAll<HTMLElement>('[data-actor="agent"]')) {
    expect(within(el).queryAllByRole("button")).toEqual([]);
    expect(el.closest("button")).toBeNull();
  }
}

describe("HOME-02 detail · decision (a, b)", () => {
  it("a: the §754 card renders from the C3 read: KV rows, why, options, evidence by source", async () => {
    show("a");
    const pane = await detail("decision");
    expect(pane.textContent).toContain("Recommend a §754 election for the 6/30/2025 transfer?");
    expect(pane.textContent).toContain("Daniel Reyes · Engagement partner");
    expect(pane.textContent).toContain("2025 Form 1065 · Ridgeline Property Partners, LP");
    expect(pane.textContent).toContain("Sep 15, 2026 · with the return (Reg. §1.754-1(b))");
    await waitFor(() => {
      expect(pane.textContent).toContain("Accrued Agent · run by Olivia Brandt · Sep 11");
    });
    expect(pane.textContent).toContain("Why This Was Surfaced");
    expect(within(pane).getAllByRole("radio")).toHaveLength(3);
    // The recommendation is a tag on option 2, never a choice made.
    const tagged = pane.querySelector('[data-option="file_without"]');
    expect(tagged?.textContent).toContain("Agent recommendation");
    expect(
      within(pane)
        .getAllByRole("radio")
        .some((r) => r.getAttribute("aria-checked") === "true"),
    ).toBe(false);
    await waitFor(() => {
      const sources = [...pane.querySelectorAll('[data-home02="source"]')].map(
        (s) => s.textContent,
      );
      expect(sources).toEqual([
        "Membership interest transfer agreement — Pell Street Ventures LLC to Pell Street II LLC · 2 citations",
        "Basis at 12/31/2025 (TXP-08) · 1 citation",
        "Ridgeline LPA · Article 9 Transfers · 1 citation",
      ]);
    });
    expect(footer().textContent).toContain(
      "Reserved to the engagement partner. The agent cannot decide.",
    );
    verbsAreHumanActions();
    noControlOnAgent();
  });

  it("a: Decide stays disabled until an option and a rationale exist (DV-1), then sends both", async () => {
    const seen = show("a");
    const pane = await detail("decision");
    const decide = await within(footer()).findByRole("button", { name: /Decide/u });
    expect(decide.getAttribute("data-human-verb")).toBe("Decide");
    expect((decide as HTMLButtonElement).disabled).toBe(true);
    // The agent's recommended option alone is not enough.
    fireEvent.click(within(pane).getAllByRole("radio")[1] as HTMLElement);
    expect((decide as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(pane).getByRole("textbox"), {
      target: { value: "Model the cost segregation first." },
    });
    await waitFor(() => {
      expect((decide as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(decide);
    await waitFor(() => {
      expect(seen.posts.map((p) => p.path)).toContain(`/v1/decision-cards/${DECISION_754}/decide`);
    });
    const sent = seen.posts.find((p) => p.path.endsWith("/decide"))?.body as Record<
      string,
      unknown
    >;
    expect(sent.option_key).toBe("file_without");
    expect(sent.rationale).toBe("Model the cost segregation first.");
    // b: the detail keeps the decided card after the gate leaves the queue.
    expect(await screen.findByText("Decided · Daniel Reyes · 9:36 AM")).toBeTruthy();
  });

  it("a: Request more analysis… opens SHL-11 over the queue", async () => {
    const seen = show("a");
    await detail("decision");
    fireEvent.click(
      await waitFor(() =>
        within(footer()).getByRole("button", { name: "Request more analysis…" }),
      ),
    );
    await waitFor(() => {
      expect(seen.search().ov).toBe(`decision:${DECISION_754}`);
    });
  });

  it("b: decided: the pill, the chosen option only, the owner's note, no Decide", async () => {
    show("b");
    const pane = await detail("decision");
    expect(await within(pane).findByText("Decided · Daniel Reyes · 9:36 AM")).toBeTruthy();
    expect(within(pane).getAllByRole("radio")).toHaveLength(1);
    expect(
      await screen.findByText(
        "Waiting on client: §754 decision sent to Owen Calder via the portal (POR-04).",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Decide/u })).toBeNull();
    expect(within(pane).queryByRole("textbox")).toBeNull();
  });

  it("not the reserved person: radios disabled, no Decide, the reserved line stays", async () => {
    show("a", {
      "GET /v1/decision-cards/{card_id}": async () => {
        const { card754 } = await import("../../fixtures/seed/approvals-detail");
        return json({ ...card754, card: { ...card754.card, allowed_actions: [] } });
      },
    });
    const pane = await detail("decision");
    await waitFor(() => {
      expect(
        within(pane)
          .getAllByRole("radio")
          .every((r) => r.hasAttribute("disabled")),
      ).toBe(true);
    });
    expect(screen.queryByRole("button", { name: /Decide/u })).toBeNull();
    expect(footer().textContent).toContain("The agent cannot decide.");
  });
});

describe("HOME-02 detail · sign-offs (c, d)", () => {
  it("c: blocked: KV rows, the banner in words, Sign off… disabled, Open proposal opens SHL-10", async () => {
    const seen = show("c");
    const pane = await detail("sign_off");
    expect(pane.textContent).toContain("Capital Accounts — Ridgeline 2025 Form 1065");
    expect(pane.textContent).toContain("Capital Accounts · Version 3");
    expect(pane.textContent).toContain("Partner (L4)");
    expect(pane.textContent).toContain("Prepared · OB");
    expect(pane.textContent).toContain("Reviewed · SI");
    expect(pane.querySelector('[data-home02="blocked"]')?.textContent).toBe(
      "Cannot sign off: M-2 ties · off 6,200. The fix (add tax-exempt interest 6,200 as other increase) is proposed by Accrued Agent and awaits Samuel Ito.",
    );
    const sign = await within(footer()).findByRole("button", { name: "Sign off…" });
    expect(sign.getAttribute("data-human-verb")).toBe("Sign off");
    expect((sign as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(footer()).getByRole("button", { name: "Open proposal" }));
    await waitFor(() => {
      expect(seen.search().ov).toBe(`approve:${M2_FIX}`);
    });
  });

  it("d: ready: Sign off… opens SHL-12 at Partner (L4)", async () => {
    const seen = show("d");
    const pane = await detail("sign_off");
    expect(pane.textContent).toContain("Summary & preparer memo — Ridgeline 2025 Form 1065");
    expect(pane.querySelector('[data-home02="blocked"]')).toBeNull();
    expect(footer().textContent).toContain("Signs off at Partner (L4).");
    const sign = await within(footer()).findByRole("button", { name: "Sign off…" });
    expect((sign as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(sign);
    await waitFor(() => {
      expect(String(seen.search().ov)).toMatch(/^signoff:return_section:[0-9a-f-]+:L4_partner$/u);
    });
    verbsAreHumanActions();
  });
});

describe("HOME-02 detail · agent outputs (g)", () => {
  it("g: Reasoning card, Source row, Approve adjustments opens SHL-10; the agent owns no control", async () => {
    const seen = show("g");
    const pane = await detail("proposal");
    expect(pane.textContent).toContain(
      "Classify the Ridgeline K-1 as passive on the Feld return?",
    );
    expect(pane.textContent).toContain("2025 Form 1040 · Jonah & Claire Feld");
    await waitFor(() => {
      expect(pane.textContent).toContain("Accrued Agent · run by Kevin Osei");
    });
    expect(pane.textContent).toContain("Manager (L3)");
    expect(pane.textContent).toContain(
      "Prior-year treatment and the current K-1 support passive activity classification.",
    );
    expect(pane.querySelector('[data-home02="source"]')?.textContent).toBe(
      "2025 Schedule K-1 · 2 citations",
    );
    expect(footer().textContent).toContain("The agent cannot approve its own work.");
    const approve = within(footer()).getByRole("button", { name: /Approve adjustments/u });
    expect(approve.getAttribute("data-human-verb")).toBe("Approve");
    noControlOnAgent();
    fireEvent.click(approve);
    await waitFor(() => {
      expect(seen.search().ov).toBe(`approve:${FELD_PROPOSAL}`);
    });
  });
});

describe("HOME-02 detail · approvals, sends and the fallback", () => {
  it("final approval opens SHL-12's final approval for the return", async () => {
    const seen = show("a", {}, null);
    await detail("decision");
    const row = [...document.querySelectorAll<HTMLButtonElement>("[data-issue-row]")].find((r) =>
      r.textContent.startsWith("Final approval & export"),
    );
    fireEvent.click(row as HTMLButtonElement);
    await detail("generic");
    const approve = within(footer()).getByRole("button", { name: "Final approval…" });
    expect(approve.getAttribute("data-human-verb")).toBe("Approve");
    fireEvent.click(approve);
    await waitFor(() => {
      expect(String(seen.search().ov)).toMatch(/^signoff:tax_return:[0-9a-f-]+:L4_partner$/u);
    });
  });

  it("an unknown subkind renders the generic detail with its facts, never hidden (AC7.8)", async () => {
    const odd: HumanGateOut = {
      id: "00000000-0000-4000-8000-0000000000aa",
      kind: "evidence_review",
      subkind: "upload_awaiting_review",
      band: "approvals_sends",
      subject: { type: "evidence_version", id: "00000000-0000-4000-8000-0000000000ab" },
      engagement_id: null,
      work_item_id: null,
      client_id: null,
      assignee_user_id: null,
      role: null,
      due_on: "2026-09-16",
      state: "open",
      created_at: "2026-09-14T14:00:00Z",
      office_id: null,
      blocked: false,
      blocked_reason_code: null,
      title: "Review upload — Northwind census file",
      context: "Uploaded by the client Sep 13",
    };
    show("a", humanGateHandlers(getSeed(), { rows: () => [odd] }), odd.id);
    const pane = await detail("generic");
    expect(pane.getAttribute("data-subkind")).toBe("upload_awaiting_review");
    expect(pane.textContent).toContain("Review upload — Northwind census file");
    expect(pane.textContent).toContain("Uploaded by the client Sep 13");
  });
});
