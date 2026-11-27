// C-01-T37 (TASK-8533): CLS-04 Accounts in fixture mode. Row acceptance: "The tree foots
// (539,055.45 = 163,543.05 + 375,512.40), no Post AJE control renders, and b2 and c stay absent
// until C-02."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { copperleafAccountTree } from "../../fixtures/seed/close-accounts";
import { CLOSE_IDS } from "../../fixtures/seed/closes";
import { newQueryClient } from "../../testing/support";
import { CLS04, type CLS04Props } from "./index";
import { type Cls04State, INITIAL, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Cls04State, props: Partial<CLS04Props> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLS04 closeId={CLOSE_IDS.august} initial={INITIAL[state]} {...props} />
    </QueryClientProvider>,
  );
}

async function tree(): Promise<void> {
  await waitFor(() => {
    expect(document.querySelector("[data-node='Prepaid Insurance']")).not.toBeNull();
  });
}

const cents = (v: string): number => Math.round(Number(v) * 100);

describe("CLS-04 Accounts", () => {
  it.each(["a", "cprime"] as const)("the tree foots: assets = liabilities + equity (%s)", (st) => {
    const t = copperleafAccountTree(st);
    const [asset, liability, equity] = t.nodes;
    expect(cents(asset?.balance ?? "")).toBe(
      cents(liability?.balance ?? "") + cents(equity?.balance ?? ""),
    );
    for (const cls of t.nodes) {
      const sum = (cls.children ?? []).reduce((s, c) => s + cents(c.balance), 0);
      expect(sum).toBe(cents(cls.balance));
    }
    expect(t.nodes.map((n) => n.balance).slice(0, 3)).toEqual(
      st === "a"
        ? ["539055.45", "163543.05", "375512.40"]
        : ["538355.45", "163543.05", "374812.40"],
    );
  });

  // C-01 DV-1: without W1 posting (attest clients, firms without W1) no state posts. C-02-T56's
  // W1 states (bpost, b2, c) are tested below.
  it.each(["a", "a2", "b", "cprime", "d", "e", "f"] as const satisfies readonly Cls04State[])(
    "renders %s with no Post AJE control",
    async (st) => {
      show(st);
      await tree();
      expect(screen.queryByRole("button", { name: /post aje/i })).toBeNull();
      expect(document.body.textContent).not.toMatch(/Posted · QBO/u);
    },
  );

  it("a: Prepaid Insurance ties once posted, GL 3,500 against the schedule 2,800", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelector("[data-cls04='workpaper']")?.getAttribute("data-tally")).toBe(
        "ties_once_posted",
      );
    });
    expect(document.querySelector("[data-gl='2026-08']")?.textContent).toBe("$3,500");
  });

  it("b: approved is read-only, with the record-in-QuickBooks note", async () => {
    show("b");
    await waitFor(() => {
      expect(document.querySelector("[data-cls04='read-only']")).not.toBeNull();
    });
    expect(document.body.textContent).toContain("Approved by RM under BH AJE thresholds v2");
    expect(document.body.textContent).toContain(
      "Record it in QuickBooks; the next sync ties the schedule",
    );
  });

  it("c′: recorded in QuickBooks by the sync; August GL 2,800 ties", async () => {
    show("cprime");
    await waitFor(() => {
      expect(document.body.textContent).toContain(
        "Recorded in QuickBooks · JE 48214 · found by sync 10:20",
      );
    });
    expect(document.querySelector("[data-gl='2026-08']")?.textContent).toBe("$2,800");
  });

  it("d: does not tie, off 60.00 to its review issue", async () => {
    const onIssue = vi.fn();
    show("d", { onIssue });
    await waitFor(() => {
      expect(document.querySelector("[data-cls04='workpaper']")?.getAttribute("data-tally")).toBe(
        "off",
      );
    });
    screen.getByRole("button", { name: "Open the review issue" }).click();
    expect(onIssue).toHaveBeenCalledOnce();
  });

  it("e: the Detail register lists the premium and seven amortizations", async () => {
    show("e");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-register-line]").length).toBe(8);
    });
  });

  it("f: a bank leaf reads Reconciliation and opens CLS-05", async () => {
    const onReconciliation = vi.fn();
    show("f", { onReconciliation });
    await tree();
    expect(document.querySelector("[data-cls04='bank']")).not.toBeNull();
    screen.getByRole("button", { name: "Open reconciliation" }).click();
    expect(onReconciliation).toHaveBeenCalledWith("35");
  });

  it("a2: the add-arrangement drawer is open", async () => {
    show("a2");
    await tree();
    expect(document.querySelector("[data-cls04='arrangement']")).not.toBeNull();
  });

  // --- C-02-T56 (TASK-9027; DEC-6032): posting restored for non-attest W1 clients -----------

  it("CLS-04 b (W1): an approved non-attest entry offers Post AJE…", async () => {
    show("bpost");
    await tree();
    const post = await screen.findByRole("button", { name: "Post AJE…" });
    expect(post.getAttribute("data-variant")).toBe("primary");
    expect(document.querySelector("[data-cls04='read-only']")).toBeNull();
  });

  it("CLS-04 b2 acceptance: the confirm posts AJE-02 as a batch of one", async () => {
    const calls: { path: string; body: unknown }[] = [];
    const base = scenarios.b2;
    restore = installFixtureMode({
      ...base,
      handlers: {
        ...base.handlers,
        "POST /v1/work-items/{work_item_id}/posting-batches": (request) => {
          calls.push({ path: request.path, body: request.body });
          return json(
            {
              batch_id: "b",
              batch_code: "2026-08-A",
              period: "2026-08",
              status: "proposed",
              entry_count: 1,
              total_amount: "700.00",
              version: 1,
            },
            202,
          );
        },
      },
    });
    render(
      <QueryClientProvider client={newQueryClient()}>
        <CLS04 closeId={CLOSE_IDS.august} initial={INITIAL.b2} />
      </QueryClientProvider>,
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Post AJE-02 to QuickBooks Online?",
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Post" }));
    await waitFor(() => {
      expect(calls).toHaveLength(1);
    });
    const body = calls[0]?.body as { entry_ids: string[]; seen_versions: Record<string, number> };
    expect(body.entry_ids).toHaveLength(1);
    expect(Object.values(body.seen_versions)).toEqual([2]);
  });

  it("CLS-04 c acceptance: Posted · QBO 48214, and Post AJE reads Posted", async () => {
    show("c");
    await tree();
    expect(await screen.findByText("Posted · QBO 48214 · 10:20 AM")).toBeTruthy();
    const posted = screen.getByRole("button", { name: "Posted" });
    expect(posted.hasAttribute("disabled")).toBe(true);
  });
});
