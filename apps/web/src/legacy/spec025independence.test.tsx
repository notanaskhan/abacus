// SPEC-025 AC-7 per person (TASK-045): until the person confirms, the engagement says why client
// data is closed to them and lets them answer there.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { json, mockApi, renderRoutes } from "../testing/support";
import { IndependenceBanner } from "./MyConfirmations";

const E = "e1";
const HEADING = { name: "Confirm your independence to see client data" };
const OPEN = {
  engagement_id: E,
  engagement_name: "FY2026",
  client_name: "Northwind",
  status: "requested",
  statement: "I confirm I am independent of Northwind for this engagement.",
};

afterEach(cleanup);

function renderBanner(): void {
  renderRoutes([{ path: "/", component: () => <IndependenceBanner engagementId={E} /> }]);
}

describe("SPEC-025 AC-7 per person (TASK-045)", () => {
  it("test_ac7_an_unconfirmed_member_sees_the_banner_and_confirms_there", async () => {
    let answered = false;
    const api = mockApi({
      "GET /v1/firm/confirmations": () => json(answered ? [] : [OPEN]),
      [`POST /v1/engagements/${E}/independence`]: () => {
        answered = true;
        return json({
          acceptance: null,
          letter: null,
          confirmations: [],
          letter_required: false,
          blocked: null,
        });
      },
    });
    renderBanner();
    expect(await screen.findByRole("heading", HEADING)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => {
      expect(screen.queryByRole("heading", HEADING)).toBeNull();
    });
    const post = api.calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ confirm: true });
  });

  it("test_ac7_no_banner_on_another_engagement_or_once_confirmed", async () => {
    const api = mockApi({
      "GET /v1/firm/confirmations": () => json([{ ...OPEN, engagement_id: "e2" }]),
    });
    renderBanner();
    await waitFor(() => {
      expect(api.calls.length).toBeGreaterThan(0);
    });
    expect(screen.queryByRole("heading", HEADING)).toBeNull();
  });
});
