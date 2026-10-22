// SPEC-027 (TASK-050): the activity feed in plain words, and the engagement's pause switch.
import type { ActivityOut, AgentOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { json, mockApi, never, renderRoutes } from "../testing/support";
import { AgentActivity, AgentControls } from "./AgentActivity";

const E = "e1";
const ME = { user_id: "u-m", display_name: "Maya", memberships: [], active_tenant_id: "t1" };
const ON: AgentOut = {
  enabled: true,
  paused_at: null,
  paused_by: null,
  reason: null,
  firm_paused_at: null,
};

function row(over: Partial<ActivityOut>): ActivityOut {
  return {
    id: crypto.randomUUID(),
    policy: "P-1",
    policy_version: 1,
    action: "screening.start",
    outcome: "done",
    reason: null,
    record_type: "evidence_version",
    record_id: "v1",
    item_count: null,
    created_at: "2026-10-10T09:00:00Z",
    ...over,
  };
}

afterEach(cleanup);

function renderOne(component: () => JSX.Element): void {
  renderRoutes([{ path: "/", component }]);
}

describe("SPEC-027 activity feed (TASK-050)", () => {
  it("test_ac7_says_what_happened_and_why_in_plain_words", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/activity`]: () =>
        json([
          row({}),
          row({
            policy: "P-2",
            action: "retrieval.start",
            outcome: "skipped",
            reason: "not_open",
          }),
          row({ policy: "P-3", action: "match.suggested", item_count: 3 }),
        ]),
    });
    renderOne(() => <AgentActivity engagementId={E} />);
    expect(await screen.findByText("Screen new evidence")).toBeTruthy();
    expect(
      screen.getByText(
        "Skipped: retrieve from the client's system, because the engagement isn't open to client data yet",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText("Suggested request items for a file in the inbox: 3 suggestions"),
    ).toBeTruthy();
  });

  it("test_ac10_empty_loading_and_not_allowed_states", async () => {
    mockApi({ [`GET /v1/engagements/${E}/activity`]: () => json([]) });
    renderOne(() => <AgentActivity engagementId={E} />);
    expect(await screen.findByText("Nothing yet")).toBeTruthy();
    cleanup();
    mockApi({ [`GET /v1/engagements/${E}/activity`]: () => json({ detail: "forbidden" }, 403) });
    renderOne(() => <AgentActivity engagementId={E} />);
    expect(await screen.findByText("Not available")).toBeTruthy();
    cleanup();
    mockApi({ [`GET /v1/engagements/${E}/activity`]: never });
    const { container } = renderRoutes([
      { path: "/", component: () => <AgentActivity engagementId={E} /> },
    ]);
    await waitFor(() => {
      expect(container.querySelector(".animate-pulse")).not.toBeNull();
    });
  });
});

describe("SPEC-027 pause switch (TASK-050)", () => {
  it("test_ac6_a_manager_pauses_with_a_reason", async () => {
    let state = ON;
    const api = mockApi({
      "GET /v1/me": () => json(ME),
      [`GET /v1/engagements/${E}/team`]: () =>
        json([{ user_id: "u-m", display_name: "Maya", role: "manager" }]),
      [`GET /v1/engagements/${E}/agent`]: () => json(state),
      [`POST /v1/engagements/${E}/agent/pause`]: () => {
        state = {
          ...ON,
          paused_at: "2026-10-10T10:00:00Z",
          paused_by: "Maya",
          reason: "client asked",
        };
        return json(state);
      },
      [`GET /v1/engagements/${E}/activity`]: () => json([]),
    });
    renderOne(() => <AgentControls engagementId={E} />);
    expect(await screen.findByText("Agent on")).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Pause" }));
    fireEvent.change(screen.getByLabelText("Why you're pausing (optional)"), {
      target: { value: "client asked" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Pause the agent" }));
    expect(await screen.findByText("Agent paused")).toBeTruthy();
    expect(api.calls.find((c) => c.method === "POST")?.body).toEqual({ reason: "client asked" });
  });

  it("test_ac6_staff_see_the_state_but_no_switch", async () => {
    mockApi({
      "GET /v1/me": () => json(ME),
      [`GET /v1/engagements/${E}/team`]: () =>
        json([{ user_id: "u-m", display_name: "Maya", role: "staff" }]),
      [`GET /v1/engagements/${E}/agent`]: () =>
        json({ ...ON, firm_paused_at: "2026-10-10T08:00:00Z" }),
    });
    renderOne(() => <AgentControls engagementId={E} />);
    expect(await screen.findByText("Agents paused by your firm")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Pause" })).toBeNull();
  });

  it("test_nothing_shows_when_the_agent_is_off_for_the_firm", async () => {
    const api = mockApi({
      [`GET /v1/engagements/${E}/agent`]: () => json({ ...ON, enabled: false }),
    });
    renderOne(() => <AgentControls engagementId={E} />);
    await waitFor(() => {
      expect(api.calls.length).toBeGreaterThan(0);
    });
    expect(screen.queryByText("Agent on")).toBeNull();
  });
});
