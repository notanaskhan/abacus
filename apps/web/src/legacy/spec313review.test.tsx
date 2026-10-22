// SPEC-313 (TASK-331): review notes on a reviewable and the sign-off matrix with the G5 gate.
import type { ReviewMatrixOut, ReviewNoteOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { blockerWord, ReviewMatrix } from "./ReviewMatrix";
import { openAnchors, ReviewableNotes } from "./ReviewableNotes";

const E = "/v1/engagements/e1";
const NOTE: ReviewNoteOut = {
  id: "n1",
  target_type: "workpaper",
  target_id: "w1",
  target_code: "C-100",
  anchor: "B4",
  body: "Agree to the bank confirmation",
  status: "open",
  raised_by_name: "Hannah Leclerc",
  raised_at: "2026-10-21T10:00:00Z",
  raised_by_me: false,
  events: [],
};
const levels = (signed: number[]) =>
  (["preparer", "reviewer", "manager", "partner", "eqr"] as const).map((name, i) => ({
    level: i + 1,
    name,
    signed_by_name: signed.includes(i + 1) ? "Pat Person" : null,
    stale: false,
    required: i < 2,
  }));
const MATRIX: ReviewMatrixOut = {
  rows: [
    {
      target_type: "workpaper",
      target_id: "w1",
      code: "C-100",
      title: "Cash lead schedule",
      levels: levels([1]),
      open_notes: 1,
      status: "open_notes",
      missing: [2],
    },
    {
      target_type: "trial_balance",
      target_id: "tb1",
      code: "TB 2026-12-31",
      title: "Trial balance (standard, v1)",
      levels: levels([1, 2]),
      open_notes: 0,
      status: "complete",
      missing: [],
    },
  ],
  gate_met: false,
  blockers: ["open_notes:C-100:1", "unsigned:C-100:L2"],
};

function team(role: string) {
  return {
    [`GET ${E}/team`]: () => json([{ user_id: "u1", display_name: "Pat Person", role }]),
    "GET /v1/me": () =>
      json({ user_id: "u1", display_name: "Pat Person", memberships: [], active_tenant_id: "t1" }),
  };
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("SPEC-313 review", () => {
  it("words blockers and finds open anchors (ac4, ac5)", () => {
    expect(blockerWord("unsigned:C-100:L2")).toBe("C-100 needs L2");
    expect(blockerWord("open_notes:C-100:1")).toBe("C-100 has 1 open note");
    expect(blockerWord("nothing_to_review")).toBe("Nothing to review yet");
    expect([
      ...openAnchors([NOTE, { ...NOTE, id: "n2", anchor: "C9", status: "cleared" }]),
    ]).toEqual(["B4"]);
  });

  it("a reviewer raises a note on the selected cell (ac2)", async () => {
    const { calls } = mockApi({
      [`GET ${E}/review-notes`]: () => json([]),
      [`POST ${E}/review-notes`]: () => json([NOTE], 201),
    });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <ReviewableNotes
            engagementId="e1"
            targetType="workpaper"
            targetId="w1"
            anchor="B4"
            role="manager"
          />
        ),
      },
    ]);
    fireEvent.change(await screen.findByLabelText("New review note"), {
      target: { value: "Agree to the bank confirmation" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Raise note" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "POST")?.body).toEqual({
        target_type: "workpaper",
        target_id: "w1",
        body: "Agree to the bank confirmation",
        anchor: "B4",
      });
    });
  });

  it("the preparer answers but can't clear someone else's note (ac3)", async () => {
    const { calls } = mockApi({
      [`GET ${E}/review-notes`]: () => json([NOTE]),
      [`POST ${E}/review-notes/n1/respond`]: () => json([{ ...NOTE, status: "responded" }], 201),
    });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <ReviewableNotes engagementId="e1" targetType="workpaper" targetId="w1" role="staff" />
        ),
      },
    ]);
    expect(await screen.findByText("Agree to the bank confirmation")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
    expect(screen.queryByLabelText("New review note")).toBeNull(); // staff don't raise
    fireEvent.change(screen.getByLabelText(/Answer to/), { target: { value: "Agreed, see B4" } });
    fireEvent.click(screen.getByRole("button", { name: "Answer" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/respond"))?.body).toEqual({
        body: "Agreed, see B4",
      });
    });
  });

  it("shows the matrix, its statuses and what blocks the gate (ac4, ac5)", async () => {
    mockApi({
      ...team("manager"),
      [`GET ${E}/review-matrix`]: () => json(MATRIX),
      [`GET ${E}/review-notes`]: () => json([NOTE]),
    });
    renderRoutes([{ path: "/", component: () => <ReviewMatrix engagementId="e1" /> }]);
    expect(await screen.findByText("Review open · 2")).toBeTruthy();
    expect(screen.getByText("C-100 needs L2")).toBeTruthy();
    expect(screen.getAllByText("Open notes")).toHaveLength(2); // the column and C-100's status
    expect(screen.getByText("Complete")).toBeTruthy();
    expect(await screen.findByText("Agree to the bank confirmation")).toBeTruthy();
  });
});
