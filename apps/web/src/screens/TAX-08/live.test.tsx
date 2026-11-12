// TASK-7323 (SPEC-649 §6): TAX-08's live drawer against the generated client. Availability comes
// first (AC-6.8: no consent, no session, no model call); the first ask creates the session bound
// to the return and posts the message with an Idempotency-Key; the thread is the snapshot; a plan
// opens its run in the run pane, where the person decides.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ASSISTANT_LIVE_COPY, AssistantLive } from "./live";

const RETURN = "11111111-1111-4111-8111-111111111111";
const SESSION = "22222222-2222-4222-8222-222222222222";
const RUN = "33333333-3333-4333-8333-333333333333";

interface Call {
  key: string;
  body: unknown;
  query: string;
  idempotency: string | null;
}

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function serve(handlers: Record<string, FixtureHandler>): Call[] {
  const calls: Call[] = [];
  const wrapped = Object.fromEntries(
    Object.entries<FixtureHandler>({
      "GET /v1/me/capabilities": () => json({ flags: {}, entitlements: [] }),
      ...handlers,
    }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({
          key,
          body: request.body,
          query: request.query.toString(),
          idempotency: request.headers?.get("Idempotency-Key") ?? null,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ state: "live", persona: "samuel-ito", handlers: wrapped });
  return calls;
}

const summary = (assistant: string) => ({
  return_id: RETURN,
  review_count: 0,
  viewer_level: "manager",
  issues_open: 4,
  checkpoints_proposed: 0,
  assistant,
  allowed_actions: [],
});

const item = (seq: number, kind: string, payload: Record<string, unknown>, over = {}) => ({
  id: `00000000-0000-4000-8000-${String(seq).padStart(12, "0")}`,
  seq,
  kind,
  payload: { v: 1, ...payload },
  actor_kind: kind === "user_message" || kind === "answer" ? "human" : "agent",
  actor_name: kind === "user_message" || kind === "answer" ? "Samuel Ito" : null,
  created_at: "2026-09-14T14:29:00Z",
  ...over,
});

const snapshot = (items: unknown[], state = "live") => ({
  id: SESSION,
  title: "Assistant",
  origin: "manual",
  state,
  locked: false,
  items,
  allowed_actions: ["message", "manage"],
});

function mount(): void {
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AssistantLive returnId={RETURN} open onClose={() => undefined} />
    </QueryClientProvider>,
  );
}

describe("TAX-08 Assistant (live)", () => {
  it("AC-6.8: without the §7216 consent the drawer says so and opens nothing", async () => {
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary("consent_required")),
    });
    mount();
    expect(await screen.findByText(ASSISTANT_LIVE_COPY.consent)).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(calls.some((c) => c.key.startsWith("POST /v1/workbench/sessions"))).toBe(false);
  });

  it("a firm-wide stop reads as paused, and nothing opens", async () => {
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary("agents_off")),
    });
    mount();
    expect(await screen.findByText(ASSISTANT_LIVE_COPY.agentsOff)).toBeTruthy();
    expect(calls.some((c) => c.key.startsWith("POST"))).toBe(false);
  });

  it("AC-6.1/6.2: a new thread offers the prompts; the first ask creates the session and posts", async () => {
    let posted = false;
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary("available")),
      "POST /v1/workbench/sessions": () =>
        json({ id: SESSION, title: "Assistant", state: "live" }, 201),
      "POST /v1/workbench/sessions/{session_id}/messages": () => {
        posted = true;
        return json(
          { item_id: "i1", run_id: null, status_url: `/v1/workbench/sessions/${SESSION}` },
          202,
        );
      },
      "GET /v1/workbench/sessions/{session_id}": () =>
        json(
          snapshot(
            posted
              ? [
                  item(1, "user_message", { body: "What's left before partner review?" }),
                  item(2, "agent_blocks", {
                    blocks: { version: 1, parts: [{ kind: "paragraph", text: "Two documents." }] },
                  }),
                ]
              : [],
          ),
        ),
    });
    mount();
    const prompt = await screen.findByRole("button", {
      name: "What's left before partner review?",
    });
    expect(
      screen.getByRole("button", { name: "Explain the 2025 vs 2024 change in total tax" }),
    ).toBeTruthy();
    fireEvent.click(prompt);
    await waitFor(() => {
      expect(calls.some((c) => c.key.endsWith("/messages"))).toBe(true);
    });
    expect(calls.find((c) => c.key === "POST /v1/workbench/sessions")?.body).toEqual({
      subject_ref: { kind: "tax_return", id: RETURN },
    });
    const message = calls.find((c) => c.key.endsWith("/messages"));
    expect(message?.body).toEqual({ body: "What's left before partner review?" });
    expect(message?.idempotency).toMatch(/^[0-9a-f-]{36}$/);
    expect(await screen.findByText("What's left before partner review?")).toBeTruthy();
    expect(
      document.querySelector("[data-item='agent_blocks'] [data-agent-blocks]"),
    ).not.toBeNull();
  });

  it("a 409 on create names the reason, and no message is posted", async () => {
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary("available")),
      "POST /v1/workbench/sessions": () =>
        json({ detail: "capability_unavailable", facts: { reason: "consent_7216" } }, 409),
    });
    mount();
    fireEvent.click(
      await screen.findByRole("button", { name: "What's left before partner review?" }),
    );
    expect((await screen.findByRole("alert")).textContent).toBe(ASSISTANT_LIVE_COPY.consent);
    expect(calls.some((c) => c.key.endsWith("/messages"))).toBe(false);
  });

  it("History lists this return's threads; one opens its snapshot, and an open question takes the answer", async () => {
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary("available")),
      "GET /v1/workbench/sessions": () =>
        json({ items: [{ id: SESSION, title: "Ridgeline K-1", state: "awaiting_answer" }] }),
      "GET /v1/workbench/sessions/{session_id}": () =>
        json(
          snapshot(
            [
              item(1, "user_message", { body: "Is Ridgeline passive?" }),
              item(2, "question", { question: { text: "Which tax year?" } }),
            ],
            "awaiting_answer",
          ),
        ),
      "POST /v1/workbench/sessions/{session_id}/messages": () =>
        json({ item_id: "i3", run_id: null, status_url: "/" }, 202),
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ridgeline K-1" }));
    expect(await screen.findByText("Which tax year?")).toBeTruthy();
    expect(calls.find((c) => c.key === "GET /v1/workbench/sessions")?.query).toBe(
      `subject_ref=${encodeURIComponent(`tax_return:${RETURN}`)}`,
    );
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "2025" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => {
      expect(calls.find((c) => c.key.endsWith("/messages"))?.body).toEqual({
        body: "2025",
        answers_seq: 2,
      });
    });
  });

  it("a plan opens its run in the run pane; the drawer itself offers no approve", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary("available")),
      "GET /v1/workbench/sessions": () =>
        json({ items: [{ id: SESSION, title: "Box 18A", state: "live" }] }),
      "GET /v1/workbench/sessions/{session_id}": () =>
        json(
          snapshot([
            item(1, "user_message", { body: "Fix box 18A" }),
            item(
              2,
              "plan",
              { steps: [{ key: "s1", label: "Propose line 2a 1,550", writes: true }] },
              { run_id: RUN },
            ),
          ]),
        ),
      "GET /v1/agent-runs/{run_id}": () => json({ detail: "not_found" }, 404),
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "Box 18A" }));
    expect(await screen.findByText("Propose line 2a 1,550")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: ASSISTANT_LIVE_COPY.openPlan }));
    await waitFor(() => {
      expect(document.querySelector("[data-run-pane]")).not.toBeNull();
    });
  });
});
