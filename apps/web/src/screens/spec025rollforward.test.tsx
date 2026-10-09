// SPEC-025 AC-2 (TASK-048): review last year's team, template and items; create what's ticked.
import type { EngagementIn, RollForwardProposalOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes } from "../testing/support";
import { RollForwardReview } from "./RollForward";

const BODY: EngagementIn = {
  name: "FY2026",
  client_name: "Halvorsen",
  client_entity_name: "Halvorsen Logistics",
  fiscal_period_start: "2026-01-01",
  fiscal_period_end: "2026-12-31",
  type: "audit",
  client_id: "c1",
  client_entity_id: "e1",
};

const PROPOSAL: RollForwardProposalOut = {
  prior: {
    engagement_id: "p1",
    name: "FY2025",
    fiscal_period_start: "2025-01-01",
    fiscal_period_end: "2025-12-31",
  },
  others: [],
  team: [
    { user_id: "u-sam", display_name: "Sam Patel", role: "senior", available: true },
    { user_id: "u-left", display_name: "Lee Gone", role: "staff", available: false },
  ],
  template: {
    template_id: "t1",
    template_name: "Audit core",
    version_last_year: 3,
    latest_version_id: "v4",
    latest_version: 4,
  },
  items: [
    {
      kind: "used",
      description: "Bank statements",
      audit_area: "Cash",
      tier: "A",
      client_visible: true,
      ticked: true,
      prior_item_id: "i1",
      template_key: null,
    },
    {
      kind: "not_used",
      description: "Petty cash count",
      audit_area: "Cash",
      tier: null,
      client_visible: false,
      ticked: false,
      prior_item_id: "i2",
      template_key: null,
    },
    {
      kind: "new_in_template",
      description: "Bank confirmations",
      audit_area: "Cash",
      tier: "B",
      client_visible: false,
      ticked: true,
      prior_item_id: null,
      template_key: 7,
    },
  ],
};

afterEach(cleanup);

describe("SPEC-025 AC-2 roll-forward review (TASK-048)", () => {
  it("test_ac2_shows_the_proposal_and_creates_exactly_what_is_ticked", async () => {
    const created = vi.fn();
    const { calls } = mockApi({
      "POST /v1/engagements": () => json({ id: "new", name: "FY2026", team: [] }, 201),
    });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <RollForwardReview
            proposal={PROPOSAL}
            body={BODY}
            onBack={() => undefined}
            onChoosePrior={() => undefined}
            onCreated={created}
          />
        ),
      },
    ]);
    expect(await screen.findByText(/Rolling forward from/)).toBeTruthy();
    expect(screen.getByText("Audit core · v4 (v3 last year)")).toBeTruthy();
    expect(
      screen.getByText("1 of 2 used last year, 1 not used, 1 new in the template."),
    ).toBeTruthy();
    expect(screen.getByText(/left the firm or now walled/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Role for Sam Patel"), {
      target: { value: "manager" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /Petty cash count/ }));
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));
    await waitFor(() => {
      expect(created).toHaveBeenCalledWith("new");
    });
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({
      ...BODY,
      roll_forward: {
        prior_engagement_id: "p1",
        team: [{ user_id: "u-sam", role: "manager" }],
        version_id: "v4",
        prior_item_ids: ["i1", "i2"],
        template_keys: [7],
      },
    });
  });

  it("test_ac2_a_refusal_is_shown_and_nothing_opens", async () => {
    const created = vi.fn();
    mockApi({
      "POST /v1/engagements": () => json({ detail: "team_member_unavailable" }, 409),
    });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <RollForwardReview
            proposal={PROPOSAL}
            body={BODY}
            onBack={() => undefined}
            onChoosePrior={() => undefined}
            onCreated={created}
          />
        ),
      },
    ]);
    fireEvent.click(await screen.findByRole("button", { name: "Create engagement" }));
    expect(await screen.findByText("Couldn't create the engagement")).toBeTruthy();
    expect(created).not.toHaveBeenCalled();
  });
});
