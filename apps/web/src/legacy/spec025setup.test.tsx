// SPEC-025 AC-10 (TASK-046): the setup page — summary, checklist, reasons — and opening on it.
import type { SetupOut } from "@abacus/api-client";
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { json, mockApi, never, renderRoutes } from "../testing/support";
import { DefaultToSetup, Setup } from "./Setup";

const E = "e1";
const SETUP: SetupOut = {
  acceptance: null,
  letter: null,
  confirmations: [],
  letter_required: false,
  blocked: "acceptance_missing",
  summary:
    "Northwind FY2026 audit (continuance): waiting for Dana Lee to record continuance. 0 of 2 have confirmed independence.",
  steps: [
    {
      key: "acceptance",
      label: "Continuance",
      state: "waiting",
      detail: "Not recorded yet",
      next: "Dana Lee (engagement partner)",
      reason: null,
    },
    {
      key: "client_contacts",
      label: "Client contacts",
      state: "blocked",
      detail: "0 joined, 0 invited",
      next: null,
      reason: "Client invitations open once Dana Lee records acceptance.",
    },
    {
      key: "letter",
      label: "Engagement letter",
      state: "warning",
      detail: "Not recorded yet",
      next: "Dana Lee (partner or manager)",
      reason: "Preferably signed before work starts.",
    },
  ],
};

afterEach(cleanup);

function renderSetup(): void {
  renderRoutes([{ path: "/", component: () => <Setup engagementId={E} /> }]);
}

describe("SPEC-025 AC-10 setup page (TASK-046)", () => {
  it("test_ac10_shows_the_summary_the_checklist_and_a_reason_on_every_blocked_item", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/setup`]: () => json(SETUP),
      [`GET /v1/engagements/${E}/team`]: () => json([]),
    });
    renderSetup();
    expect(await screen.findByText(SETUP.summary)).toBeTruthy();
    expect(screen.getByText("Continuance")).toBeTruthy();
    expect(screen.getByText("Next: Dana Lee (engagement partner)")).toBeTruthy();
    expect(screen.getByText("Blocked")).toBeTruthy();
    expect(
      screen.getByText("Client invitations open once Dana Lee records acceptance."),
    ).toBeTruthy();
    expect(screen.getByText("Preferably signed before work starts.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to People" })).toBeTruthy();
  });

  it("test_ac9_loading_state", async () => {
    mockApi({ [`GET /v1/engagements/${E}/setup`]: never });
    const { container } = renderRoutes([
      { path: "/", component: () => <Setup engagementId={E} /> },
    ]);
    await waitFor(() => {
      expect(container.querySelector(".animate-pulse")).not.toBeNull();
    });
  });

  it("test_ac9_not_allowed_state", async () => {
    mockApi({ [`GET /v1/engagements/${E}/setup`]: () => json({ detail: "forbidden" }, 403) });
    renderSetup();
    expect(await screen.findByText("Not available")).toBeTruthy();
  });

  it("test_ac9_error_state", async () => {
    mockApi({ [`GET /v1/engagements/${E}/setup`]: () => json({ detail: "boom" }, 500) });
    renderSetup();
    expect(await screen.findByText("Couldn't load the setup")).toBeTruthy();
  });

  it("test_ac10_an_engagement_not_yet_open_opens_on_setup", async () => {
    mockApi({ [`GET /v1/engagements/redirect/setup`]: () => json(SETUP) });
    renderRoutes(
      [
        {
          path: "/engagements/$engagementId",
          component: () => (
            <DefaultToSetup engagementId="redirect">
              <p>Overview here</p>
            </DefaultToSetup>
          ),
        },
        { path: "/engagements/$engagementId/setup", component: () => <p>Setup here</p> },
      ],
      { at: "/engagements/redirect" },
    );
    expect(await screen.findByText("Setup here")).toBeTruthy();
  });

  it("test_ac10_an_open_engagement_opens_on_overview", async () => {
    mockApi({ [`GET /v1/engagements/open/setup`]: () => json({ ...SETUP, blocked: null }) });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <DefaultToSetup engagementId="open">
            <p>Overview here</p>
          </DefaultToSetup>
        ),
      },
    ]);
    expect(await screen.findByText("Overview here")).toBeTruthy();
  });
});
