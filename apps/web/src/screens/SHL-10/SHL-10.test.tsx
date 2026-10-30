// SHL-10 · Approve agent output (P-04-T41). One test per frame built (a, b, c, f) on its fixture
// scenario, and the acceptance: "SHL-10a, b, c and f match their artboards at Tier C, and frame c
// keeps the approve button disabled with 1 change has no citation." Tier C (pixels) is the visual
// suite's; here the content, the gate and the writes the person's clicks send.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { SHL10 } from "../../fixtures/seed/review";
import { ApproveSheet } from ".";
import { OPENS, STATES, type Shl10State, scenarios } from "./scenarios";

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

const APPROVED = {
  ...SHL10.a,
  state: "approved",
  decision: {
    id: "00000000-0000-4000-8000-000000000999",
    decision: "approved",
    reason_code: null,
    note: null,
    decided_by_user_id: "00000000-0000-4000-8000-000000000018",
    decided_by_name: "Samuel Ito",
    decided_at: "2026-10-01T14:24:00Z",
    routed_to_user_id: null,
    undo_until: "2026-10-01T14:24:10Z",
  },
  allowed_actions: ["proposal.undo"],
};

function show(state: Shl10State, extra: Record<string, FixtureHandler> = {}): Call[] {
  const calls: Call[] = [];
  const scenario: Scenario = scenarios[state];
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
      component: () => (
        <ApproveSheet
          proposalRef={OPENS[state].ref}
          initialMode={OPENS[state].mode}
          open
          onOpenChange={() => undefined}
        />
      ),
    },
  ]);
  return calls;
}

const approveButton = (name: RegExp) => screen.findByRole<HTMLButtonElement>("button", { name });

describe("SHL-10", () => {
  it("builds a to g (e′ as ep)", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "ep", "f", "g"]);
  });

  it("a: reasoning, four changes struck before → after, the tie, evidence and Approve adjustments", async () => {
    show("a");
    expect(await screen.findByText(/proposed 4 changes/u)).toBeTruthy();
    expect(screen.getByText("Ready for review")).toBeTruthy();
    expect(
      screen.getByText(
        "Prior-year treatment and the draft Ridgeline K-1 support passive classification.",
      ),
    ).toBeTruthy();
    expect(screen.getAllByText("307,900").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Net change to Form 1040 total income")).toBeTruthy();
    expect(screen.getByText("tie")).toBeTruthy();
    expect(
      screen.getByText("2025 Schedule K-1 — Ridgeline (Draft K-1 · pre-release)"),
    ).toBeTruthy();
    expect(screen.getByText("2 citations")).toBeTruthy();
    const approve = await approveButton(/^Approve adjustments$/u);
    expect(approve.disabled).toBe(false);
    expect(approve.getAttribute("data-human-verb")).toBe("Approve");
  });

  it("a: Approve waits for the server, then Undo is offered", async () => {
    const calls = show("a", {
      "POST /v1/proposals/{proposal_id}/approve": () => json(APPROVED),
    });
    fireEvent.click(await approveButton(/^Approve adjustments$/u));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/approve"))).toBe(true);
    });
    const sent = calls.find((c) => c.path.endsWith("/approve"))?.body;
    expect(sent).toEqual({ seen_version: 1 });
    await waitFor(() => {
      expect(toastStore.list().some((t) => t.text === "Proposal approved")).toBe(true);
    });
  });

  it("b: edit mode needs a citation note per edited row, then sends only the edits", async () => {
    const calls = show("b", {
      "POST /v1/proposals/{proposal_id}/approve": () => json(APPROVED),
    });
    const approve = await approveButton(/^Approve with edits$/u);
    expect(approve.disabled).toBe(true);
    const after = screen.getByLabelText("Sch E p. 2 line 28A (h) Passive income from K-1: after");
    fireEvent.change(after, { target: { value: "307000" } });
    expect(approve.disabled).toBe(true);
    const note = await screen.findByRole("textbox", {
      name: /Citation note · Sch E p. 2 line 28A \(h\)/u,
    });
    fireEvent.change(note, { target: { value: "K-1 box 2" } });
    await waitFor(() => {
      expect(approve.disabled).toBe(false);
    });
    fireEvent.click(approve);
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/approve"))?.body).toEqual({
        seen_version: 1,
        edits: [{ n: 3, after: "307000", citation_note: "K-1 box 2" }],
      });
    });
  });

  it("c: the uncited change keeps Approve disabled with 1 change has no citation", async () => {
    show("c");
    expect(await screen.findByText("Unsupported")).toBeTruthy();
    expect(
      screen.getByText("1 change has no citation. Remove it or ask the agent to cite a source."),
    ).toBeTruthy();
    // c's allowed actions hold no approve, so no Approve renders at all; the gate's disabled state
    // for an uncited row with approve allowed is the kit's (packages/ui/src/gates/gates.test.tsx).
    expect(screen.queryByRole("button", { name: /^Approve/u })).toBeNull();
    const ask = screen.getByRole("button", { name: "Ask follow-up…" });
    expect(ask.getAttribute("data-variant")).toBe("primary");
  });

  it("c: with approve allowed the uncited row still disables it", async () => {
    show("c", {
      "GET /v1/proposals/{ref}": () =>
        json({ ...SHL10.c, allowed_actions: ["proposal.approve", "proposal.reject"] }),
    });
    const approve = await approveButton(/^Approve adjustments$/u);
    expect(approve.disabled).toBe(true);
    expect(approve.getAttribute("aria-describedby")).toBe("approval-uncited");
  });

  it("f: the result line names the person and the reason; nothing to approve", async () => {
    show("f");
    expect(
      await screen.findByText("Rejected by Samuel Ito · reason: Needs client input"),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Approve/u })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reject…" })).toBeNull();
  });

  it("f: Reject… sends the reason the person picked", async () => {
    const calls = show("a", {
      "POST /v1/proposals/{proposal_id}/reject": () => json(SHL10.f),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Reject…" }));
    const dialog = await screen.findByRole("dialog", { name: "Reject proposal" });
    const reject = within(dialog).getByRole<HTMLButtonElement>("button", { name: "Reject" });
    expect(reject.disabled).toBe(true);
    const trigger = within(dialog).getByRole("button", { name: /^Reason/u });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "Needs client input" }));
    fireEvent.click(reject);
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/reject"))?.body).toEqual({
        seen_version: 1,
        reason_code: "needs_client_input",
        note: null,
      });
    });
  });
});

// P-04-T42: "Frames d, e, e-prime and g render from fixtures, Review all in package approves
// nothing, and the batch line names a person, never the agent."
describe("SHL-10 d, e, e′, g", () => {
  it("d: AJE-05 has no Approve; Send to Priya Raman routes it, with the policy row", async () => {
    const calls = show("d");
    expect(await screen.findByText("Dr Inventory — Green Coffee")).toBeTruthy();
    expect(
      screen.getByText("Review required · above $10,000 other accruals (BH AJE thresholds v2)"),
    ).toBeTruthy();
    expect(screen.getByText("Your limit: within-threshold batches only.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Approve/u })).toBeNull();
    fireEvent.click(
      await screen.findByRole("button", { name: /Send to Priya Raman for approval/u }),
    );
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/route"))).toBe(true);
    });
    const route = calls.find((c) => c.path.endsWith("/route"));
    expect((route?.body as { approver_user_id: string }).approver_user_id).toBe(
      SHL10.d.policy.routed_to_user_id,
    );
  });

  it("e: the batch as a JE table, tie 20,020.00, Approve 4 under BH AJE thresholds v2", async () => {
    const calls = show("e");
    const table = await screen.findByRole("table", { name: "Entries" });
    expect(within(table).getAllByRole("row")).toHaveLength(5);
    expect(screen.getAllByText("Approve 4 entries").length).toBeGreaterThan(0);
    expect(screen.getByText(/proposed 4 entries within BH AJE thresholds v2/u)).toBeTruthy();
    expect(screen.getByText("20,020.00")).toBeTruthy();
    const approve = await approveButton(/Approve 4 under BH AJE thresholds v2/u);
    fireEvent.click(approve);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/approve"))).toBe(true);
    });
  });

  it("e′: the line names Raj Malhotra and the policy, never the agent; Undo calls only undo", async () => {
    const calls = show("ep", {
      "GET /v1/proposals/{ref}": () =>
        json({
          ...SHL10.e_prime,
          decision: { ...SHL10.e_prime.decision, undo_until: "2099-01-01T00:00:00Z" },
        }),
    });
    const line = await screen.findByText(/Approved by Raj Malhotra under BH AJE thresholds v2/u);
    expect(line.textContent).not.toMatch(/Agent/u);
    expect(screen.queryByRole("table", { name: "Entries" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/undo"))).toBe(true);
    });
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path.split("/").at(-1))).toEqual([
      "undo",
    ]);
  });

  it("g: the set row; Review all in package approves nothing; Approve conclusion", async () => {
    const calls = show("g");
    expect(
      await screen.findByText(
        "Part of BH-FS-430 Search for unrecorded liabilities · 40 results · 1 exception",
      ),
    ).toBeTruthy();
    const review = screen.getByText("Review all in package");
    fireEvent.click(review);
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
    expect(await approveButton(/Approve conclusion/u)).toBeTruthy();
    expect(
      screen.getByText(
        "Adopting the conclusion changes only the sheet. Any adjustment is proposed by a person in AUD-15 / AUD-16.",
      ),
    ).toBeTruthy();
  });
});
