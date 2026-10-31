// I-01-T20 (TASK-2803): the ADR-078 acceptance suite for HOME-02's UI (I-01-T17 detail, T19 bulk,
// reassign and snooze) and HOME-01's activity sources (T12, T23), written from I-01 §3 F7–F9 before
// T19 opens for review. Row acceptance: "The suite is committed before I-01-T19 opens for review
// and passes on main without edits by AY's session." What it holds:
//
//   1  no gate verb on an agent-owned element (INV-1), and every gate verb is a HumanAction
//   2  the rationale is required before Decide (AC7.1, DEV rationale always required)
//   3  bulk refuses blocked and open-note items: checkboxes only on bulk_eligible rows, blocked rows
//      disabled, "4 selected · Sign off 4 as Partner" into SHL-12 f with per-item results (AC8.1)
//   4  reassign lists only the server's candidates (menus open on ArrowDown, as Radix does in jsdom); reassign and snooze wait for the server
//      (never optimistic, DEC-24, AC8.2–AC8.4); a snoozed gate leaves the queue and every count
//   5  attribution through formatActor (INV-5)
//   6  allowlisted activity events only (HOME-01, I-01-T12 / T23)
import type { HomeOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { formatActor } from "@abacus/ui";
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
import { type FixtureHandler, installFixtureMode, json } from "../../../app-core/fixture-mode";
import { homeGates } from "../../../fixtures/seed/home";
import "../../../routes/firm/sheets";
import { newQueryClient } from "../../../testing/support";
import { activityLines } from "../../HOME-01";
import { HOME02 } from "..";
import { type Home02State, freshScenarios, selectedGate } from "../scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const GATE_VERB = /^(✓ )?(Decide|Approve|Sign off|Send|Release|Post)\b/u;
const DANIEL = homeGates("daniel-reyes");
const titleOf = (n: number): string => DANIEL[n - 1]?.title ?? "";

function show(
  state: Home02State,
  extra: Record<string, FixtureHandler> = {},
  gate: string | null = selectedGate(state),
): { posts: { path: string; body: unknown }[] } {
  const posts: { path: string; body: unknown }[] = [];
  const scenario = freshScenarios()[state];
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
  return { posts };
}

const queue = (): Promise<HTMLElement> =>
  waitFor(
    () => {
      const q = document.querySelector<HTMLElement>("[data-home02='queue']");
      if (q === null) throw new Error("no queue yet");
      return q;
    },
    { timeout: 6000 },
  );

const rowOf = (title: string): HTMLElement | null =>
  [...document.querySelectorAll<HTMLElement>("[data-issue-row]")].find((r) =>
    r.textContent.includes(title),
  ) ?? null;

/** A deferred response: the test decides when the server answers. */
function held(): { handler: FixtureHandler; answer: (r: Response) => void } {
  let answer: (r: Response) => void = () => undefined;
  const pending = new Promise<Response>((resolve) => {
    answer = resolve;
  });
  return {
    handler: () => pending,
    answer: (r) => {
      answer(r);
    },
  };
}

describe("1 · INV-1: no gate verb on agent-owned elements", () => {
  it.each(["a", "c", "d", "e", "g"] as const)("%s: agent text carries no control", async (s) => {
    show(s);
    await queue();
    await waitFor(() => {
      expect(document.querySelector("[data-home02-detail]")).not.toBeNull();
    });
    for (const el of document.querySelectorAll<HTMLElement>("[data-actor='agent']")) {
      expect(within(el).queryAllByRole("button")).toEqual([]);
      expect(el.closest("button")).toBeNull();
    }
    for (const b of screen.queryAllByRole("button")) {
      if (GATE_VERB.test(b.textContent.trim()) && b.closest("[data-home02='bulk-bar']") === null) {
        expect(b.getAttribute("data-human-verb")).not.toBeNull();
      }
    }
  });
});

describe("2 · the rationale is required before Decide", () => {
  it("a: Decide stays disabled with an option and no rationale", async () => {
    show("a");
    const pane = await waitFor(() => {
      const p = document.querySelector<HTMLElement>('[data-home02-detail="decision"]');
      if (p === null) throw new Error("no decision yet");
      return p;
    });
    const radios = within(pane).getAllByRole("radio");
    fireEvent.click(radios[1] as HTMLElement);
    const decide = screen.getByRole<HTMLButtonElement>("button", { name: /Decide/u });
    expect(decide.disabled).toBe(true);
  });
});

describe("3 · bulk refuses blocked and open-note items (AC8.1)", () => {
  it("e: checkboxes only on bulk-eligible rows; Capital Accounts and Basis disabled", async () => {
    show("e");
    await queue();
    fireEvent.click(screen.getByRole("button", { name: "Select" }));
    const boxes = await screen.findAllByRole("checkbox");
    const enabled = boxes.filter((b) => !(b as HTMLButtonElement).disabled);
    const disabled = boxes.filter((b) => (b as HTMLButtonElement).disabled);
    expect(enabled.map((b) => b.getAttribute("aria-label"))).toEqual(
      [4, 5, 6, 9].map((n) => `Select ${titleOf(n)}`),
    );
    expect(disabled.map((b) => b.getAttribute("aria-label"))).toEqual(
      [7, 8].map((n) => `Select ${titleOf(n)}`),
    );
    for (const b of disabled) expect(b.getAttribute("data-issue-check")).toBe("blocked");
    // Decisions, the final approval and the send carry no checkbox at all.
    for (const n of [1, 2, 3, 10, 11]) {
      expect(screen.queryByRole("checkbox", { name: `Select ${titleOf(n)}` })).toBeNull();
    }
  });

  it("e: the bar reads 4 selected and opens SHL-12 f, which shows each item's result", async () => {
    const { posts } = show("e");
    await queue();
    fireEvent.click(screen.getByRole("button", { name: "Select" }));
    for (const n of [4, 5, 6, 9]) {
      fireEvent.click(await screen.findByRole("checkbox", { name: `Select ${titleOf(n)}` }));
    }
    const bar = await waitFor(() => {
      const b = document.querySelector<HTMLElement>("[data-home02='bulk-bar']");
      if (b === null) throw new Error("no bar yet");
      return b;
    });
    expect(bar.textContent).toContain("4 selected");
    fireEvent.click(within(bar).getByRole("button", { name: "Sign off 4 as Partner" }));
    const sheet = await screen.findByRole("dialog");
    const sign = await within(sheet).findByRole<HTMLButtonElement>("button", {
      name: /Sign off 4 as Partner/u,
    });
    await waitFor(() => {
      expect(sign.disabled).toBe(false);
    });
    fireEvent.click(sign);
    await waitFor(() => {
      expect(sheet.querySelectorAll("[data-bulk-result='signed']")).toHaveLength(4);
    });
    expect(posts.some((p) => p.path === "/v1/sign-offs:bulk")).toBe(true);
  });
});

describe("4 · reassign and snooze wait for the server (AC8.2–AC8.4)", () => {
  it("d: Snooze until… Tomorrow 9 AM keeps the row until the server answers, then it leaves", async () => {
    const gate = selectedGate("d") ?? "";
    const reply = held();
    show("d", { "POST /v1/human-gates/{gate_id}/snooze": reply.handler });
    await queue();
    fireEvent.keyDown(await screen.findByRole("button", { name: "Snooze until…" }), {
      key: "ArrowDown",
    });
    fireEvent.click(await screen.findByRole("menuitem", { name: "Tomorrow 9 AM" }));
    // Never optimistic: the row and the count stand while the request is open.
    expect(rowOf(titleOf(4))).not.toBeNull();
    reply.answer(json({ gate_id: gate, until: "2026-09-15T14:00:00Z" }));
    await waitFor(() => {
      expect(rowOf(titleOf(4))).toBeNull();
    });
    expect(await screen.findByText(/Snoozed until/u)).toBeTruthy();
  });

  it("d: the snooze menu offers Today 2 PM before 2 PM, Tomorrow 9 AM and Pick date", async () => {
    show("d");
    await queue();
    fireEvent.keyDown(await screen.findByRole("button", { name: "Snooze until…" }), {
      key: "ArrowDown",
    });
    const items = (await screen.findAllByRole("menuitem")).map((m) => m.textContent.trim());
    expect(items).toEqual(["Today 2 PM", "Tomorrow 9 AM", "Pick date…"]);
  });

  it("d: Reassign… lists only the server's candidates and waits for the server", async () => {
    const reply = held();
    show("d", { "POST /v1/human-gates/{gate_id}/reassign": reply.handler });
    await queue();
    fireEvent.keyDown(await screen.findByRole("button", { name: "Reassign…" }), {
      key: "ArrowDown",
    });
    const options = (await screen.findAllByRole("menuitem")).map((m) => m.textContent.trim());
    expect(options).toEqual(["Priya Raman"]);
    fireEvent.click(screen.getByRole("menuitem", { name: "Priya Raman" }));
    expect(rowOf(titleOf(4))).not.toBeNull();
    reply.answer(json({ gate_id: selectedGate("d"), to_user_id: "x", version: 2 }));
    await waitFor(() => {
      expect(rowOf(titleOf(4))).toBeNull();
    });
    expect(await screen.findByText("Reassigned to Priya Raman")).toBeTruthy();
  });

  it("an overdue gate offers no snooze", async () => {
    show("overdue", {}, selectedGate("d"));
    await queue();
    await waitFor(() => {
      expect(document.querySelector("[data-home02-detail]")).not.toBeNull();
    });
    expect(screen.queryByRole("button", { name: "Snooze until…" })).toBeNull();
  });
});

describe("5 · attribution through formatActor (INV-5)", () => {
  it("b: the decided line names the person; the agent is named by formatActor", async () => {
    show("b");
    expect(await screen.findByText(/Decided · Daniel Reyes · 9:36 AM/u)).toBeTruthy();
    await waitFor(() => {
      expect(document.body.textContent).toContain(formatActor({ kind: "agent" }));
    });
  });
});

describe("6 · allowlisted activity events only (HOME-01)", () => {
  const ALLOWED = [
    "client_upload",
    "follow_up_sent",
    "letter_recorded",
    "agent_pre_screen",
    "inbound_mail",
    "envelope_sent",
  ];
  const row = (event_type: string): HomeOut["client_activity"][number] =>
    ({
      id: "a",
      event_type,
      occurred_at: "2026-09-14T14:00:00Z",
      client_label: "Northwind Robotics 401(k) Plan",
      actor: { type: "contact", id: null, label: "Dana Ortiz" },
      labels: { subject: "W-3", context: "" },
      facts: { count: 1 },
    }) as unknown as HomeOut["client_activity"][number];

  it("an event outside the allowlist shows only the client, never its words", () => {
    const lines = activityLines(row("review_note.created"), null, new Date());
    expect(lines.text).toBe("Northwind Robotics 401(k) Plan");
  });

  it.each(ALLOWED)("%s has its own wording", (event) => {
    const lines = activityLines(row(event), null, new Date());
    expect(lines.text).not.toBe("");
  });
});
