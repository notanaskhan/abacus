// SPEC-031 (TASK-061): the reviewer's send-back notice. Moved unchanged from spec031clienthub.test.tsx
// by R-01-T18 when the legacy client page retired; DecisionActions stays live under Review.tsx.
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { DecisionActions } from "./DecisionActions";

const E = "e1";

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("send-back notice", () => {
  it("tells the reviewer who reads the note", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/review-reason-codes/send_back`]: () => json([]),
      [`GET /v1/engagements/${E}/review-reason-codes/reject`]: () => json([]),
    });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <DecisionActions
            engagementId={E}
            versionId="v1"
            itemLabel="Bank"
            seenProposal={null}
            onSettled={() => undefined}
          />
        ),
      },
    ]);
    const select = await screen.findByDisplayValue("Accept");
    fireEvent.change(select, { target: { value: "send_back" } });
    expect(await screen.findByText("The client will see this note.")).toBeTruthy();
    fireEvent.change(select, { target: { value: "reject" } });
    expect(await screen.findByText("Only your team sees this note.")).toBeTruthy();
  });
});
