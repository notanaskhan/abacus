// P-04-T44: independent acceptance tests (ADR-078) for the E7 gate kit, SHL-10 and SHL-16, written
// from the P-04 rows and INV-1, not from the builders' tests. "Tests … pass and fail if any approve
// or sign-off control appears on an agent-owned element."
//
//   1  no gate control on an agent-owned element (HumanAction renders nothing for the agent, a
//      policy or the system; ApprovalCard draws no Approve for them)
//   2  an uncited change disables approval
//   3  never optimistic: nothing reads approved / current until the server answers
//   4  attribution through formatActor (the agent's display name comes from one place)
//   5  Undo calls only the compensating command
import { client } from "@abacus/api-client/client";
import { type Actor, ApprovalCard, HumanAction, formatActor, toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { SHL10 } from "../../fixtures/seed/review";
import { ApproveSheet } from "../../screens/SHL-10";
import { OPENS as SHL10_OPENS, scenarios as shl10 } from "../../screens/SHL-10/scenarios";
import { CheckpointDrawer } from "../../screens/SHL-16";
import { OPENS as SHL16_OPENS, scenarios as shl16 } from "../../screens/SHL-16/scenarios";
import { newQueryClient, renderRoutes } from "../../testing/support";

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

const GATE_VERBS = /^(Approve|Sign off|Release|Send|Post|Decide)\b/u;
const NOT_PEOPLE: readonly Actor[] = [
  { kind: "agent" },
  { kind: "system" },
  { kind: "policy", name: "BH AJE thresholds", version: 2 },
];

interface Call {
  method: string;
  path: string;
}

function install(scenario: Scenario, extra: Record<string, FixtureHandler> = {}): Call[] {
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...extra }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return calls;
}

/** A handler that answers only when `release` is called (to see the screen before the server). */
function held(body: unknown): { handler: FixtureHandler; release: () => void } {
  let release = (): void => undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { handler: () => gate.then(() => json(body)), release };
}

function showSheet(state: keyof typeof shl10, extra: Record<string, FixtureHandler> = {}): Call[] {
  const calls = install(shl10[state], extra);
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ApproveSheet
          proposalRef={SHL10_OPENS[state].ref}
          initialMode={SHL10_OPENS[state].mode}
          open
          onOpenChange={() => undefined}
        />
      ),
    },
  ]);
  return calls;
}

function showDrawer(
  state: keyof typeof shl16,
  extra: Record<string, FixtureHandler> = {},
): Call[] {
  const calls = install(shl16[state], extra);
  const open = SHL16_OPENS[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CheckpointDrawer
        target={{ type: open.type, id: open.id }}
        {...(open.seq === undefined ? {} : { initialSeq: open.seq })}
        open
        onOpenChange={() => undefined}
      />
    </QueryClientProvider>,
  );
  return calls;
}

describe("1 · no gate control on an agent-owned element", () => {
  it("HumanAction renders nothing for the agent, a policy or the system", () => {
    for (const actor of NOT_PEOPLE) {
      const { container } = render(
        <HumanAction verb="Approve" object="adjustments" actor={actor} />,
      );
      expect([actor.kind, container.innerHTML]).toEqual([actor.kind, ""]);
      cleanup();
    }
  });

  it("ApprovalCard draws no gate verb for the agent, a policy or the system", () => {
    for (const actor of NOT_PEOPLE) {
      render(
        <ApprovalCard
          title="Reasoning"
          actor={actor}
          rows={[{ key: "1", label: "Line", before: "1", after: "2", cites: 1 }]}
          onApprove={() => undefined}
        />,
      );
      const verbs = screen.queryAllByRole("button").filter((b) => GATE_VERBS.test(b.textContent));
      expect([actor.kind, verbs.map((b) => b.textContent)]).toEqual([actor.kind, []]);
      cleanup();
    }
  });

  it("a person sees Approve (the guard above is not vacuous)", () => {
    render(
      <ApprovalCard
        title="Reasoning"
        actor={{ kind: "human", name: "Samuel Ito" }}
        rows={[{ key: "1", label: "Line", before: "1", after: "2", cites: 1 }]}
        onApprove={() => undefined}
      />,
    );
    expect(screen.getByRole("button", { name: /^Approve/u })).toBeTruthy();
  });

  it("SHL-10: no gate verb sits inside the agent's own reasoning or rows", async () => {
    showSheet("a");
    const reasoning = await screen.findByText(SHL10.a.reasoning);
    const card = reasoning.closest("[data-gate='approval']") as HTMLElement;
    for (const part of card.querySelectorAll<HTMLElement>(
      "[data-gate='reasoning'], ul[aria-label='Changes']",
    )) {
      expect(
        within(part)
          .queryAllByRole("button")
          .filter((b) => GATE_VERBS.test(b.textContent)),
      ).toEqual([]);
    }
  });
});

describe("2 · an uncited change disables approval", () => {
  it("ApprovalCard: a row without a citation disables Approve", () => {
    render(
      <ApprovalCard
        title="Reasoning"
        actor={{ kind: "human", name: "Samuel Ito" }}
        rows={[
          { key: "1", label: "Cited", before: "1", after: "2", cites: 1 },
          { key: "2", label: "Uncited", before: null, after: "18,240", cites: 0 },
        ]}
        onApprove={() => undefined}
      />,
    );
    expect(screen.getByRole("button", { name: /^Approve/u }).hasAttribute("disabled")).toBe(true);
  });

  it("SHL-10 c: the uncited fifth change keeps Approve disabled", async () => {
    showSheet("c");
    await screen.findByText("Sch A line 5b Real estate taxes (co-op share)");
    const approve = screen.queryByRole("button", { name: /^Approve/u });
    expect(approve === null || approve.hasAttribute("disabled")).toBe(true);
  });
});

describe("3 · never optimistic", () => {
  it("SHL-10: the proposal reads approved only after the server answers", async () => {
    const approved = { ...SHL10.a, state: "approved", allowed_actions: [] };
    const server = held(approved);
    showSheet("a", { "POST /v1/proposals/{proposal_id}/approve": server.handler });
    fireEvent.click(await screen.findByRole("button", { name: /^Approve adjustments/u }));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText(/^Approved by/u)).toBeNull();
    expect(toastStore.list().map((t) => t.text)).not.toContain("Proposal approved");
    server.release();
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain("Proposal approved");
    });
  });

  it("SHL-16: Current does not move before the server answers", async () => {
    const server = held({});
    showDrawer("a", { "POST /v1/checkpoints/{checkpoint_id}/approve": server.handler });
    fireEvent.click(await screen.findByRole("button", { name: /^Approve checkpoint/u }));
    await new Promise((r) => setTimeout(r, 50));
    const six = document.querySelector<HTMLElement>('[data-checkpoint="6"]');
    expect(within(six as HTMLElement).queryByText("Current")).toBeNull();
    server.release();
  });
});

describe("4 · attribution through formatActor", () => {
  it("SHL-10 names the agent with formatActor's words", async () => {
    showSheet("a");
    expect(
      await screen.findByText(new RegExp(`^${formatActor({ kind: "agent" })} proposed`, "u")),
    ).toBeTruthy();
  });

  it("SHL-16 names the agent author with formatActor's words", async () => {
    showDrawer("a");
    const six = await waitFor(() => {
      const el = document.querySelector<HTMLElement>('[data-checkpoint="6"]');
      if (el === null) throw new Error("no card");
      return el;
    });
    expect(six.textContent).toContain(formatActor({ kind: "agent" }));
  });
});

describe("5 · Undo calls only the compensating command", () => {
  it("SHL-10: after approve, Undo posts only …/undo", async () => {
    const approved = {
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
        undo_until: "2099-01-01T00:00:00Z",
      },
      allowed_actions: ["proposal.undo"],
    };
    const calls = showSheet("a", {
      "POST /v1/proposals/{proposal_id}/approve": () => json(approved),
      "POST /v1/proposals/{proposal_id}/undo": () => json(SHL10.a),
    });
    fireEvent.click(await screen.findByRole("button", { name: /^Approve adjustments/u }));
    // The Undo is the approved toast's action (no toaster is mounted in a unit test).
    const toast = await waitFor(() => {
      const found = toastStore.list().find((t) => t.action === "Undo");
      if (found === undefined) throw new Error("no Undo toast");
      return found;
    });
    const before = calls.filter((c) => c.method !== "GET").length;
    toastStore.act(toast.id);
    await waitFor(() => {
      expect(calls.filter((c) => c.method !== "GET").length).toBeGreaterThan(before);
    });
    const after = calls.filter((c) => c.method !== "GET").slice(before);
    expect(after.map((c) => c.path.split("/").at(-1))).toEqual(["undo"]);
  });
});
