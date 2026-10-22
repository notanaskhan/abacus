// SPEC-314 (TASK-332): completion, release and archive. The server states the checklist, the
// digest and every blocker; people concur, decide, approve, release and lock.
import type { CompletionOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { CompletionRelease, completionBlocker } from "./CompletionRelease";

const E = "/v1/engagements/e1";
const item = (
  key: CompletionOut["checklist"][number]["key"],
  done: boolean,
  gate: string | null = null,
) => ({
  key,
  done,
  applicable: true,
  gate,
  blockers: [],
});
const READY: CompletionOut = {
  checklist: [
    item("accepted", true, "G1"),
    item("review_complete", true, "G5"),
    item("eqr_concurred", true, "G6"),
    item("going_concern", true),
    item("report_approved", true),
    item("rep_letter", true, "G7"),
    item("released", false, "G8"),
    item("archived", false, "G9"),
  ],
  eqr: {
    required: true,
    eqr_names: ["Thomas Whitcombe"],
    is_me: false,
    digest: [
      {
        kind: "materiality",
        title: "Materiality",
        facts: [["Overall", "252,200.00"]],
        decided: true,
      },
    ],
    digest_hash: "a".repeat(64),
    concurrence: { by_name: "Thomas Whitcombe", at: "2026-10-05T21:40:00Z", current: true },
    open_notes: 0,
  },
  going_concern: {
    id: "g1",
    choice: "no_substantial_doubt",
    emphasis: null,
    document_date: null,
    evidence_version_id: null,
    rationale: null,
    by_name: "Margaret Okonkwo",
    at: "2026-10-07T10:00:00Z",
  },
  report: null,
  rep_letter: null,
  release: null,
  archive: null,
  can_release: true,
  release_blockers: [],
  can_lock: false,
  lock_blockers: ["not_released"],
};

function page(role: string, body: CompletionOut, extra = {}) {
  const api = mockApi({
    [`GET ${E}/completion`]: () => json(body),
    [`GET ${E}/evidence-versions`]: () => json([]),
    [`GET ${E}/team`]: () => json([{ user_id: "u1", display_name: "Pat", role }]),
    "GET /v1/me": () =>
      json({ user_id: "u1", display_name: "Pat", memberships: [], active_tenant_id: "t1" }),
    ...extra,
  });
  renderRoutes([{ path: "/", component: () => <CompletionRelease engagementId="e1" /> }]);
  return api;
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

describe("SPEC-314 completion", () => {
  it("words blockers from fixed templates (ac6)", () => {
    expect(completionBlocker("G5:unsigned:C-100:L2")).toBe("C-100 needs L2");
    expect(completionBlocker("G7:rep_letter_date_mismatch")).toBe(
      "The representation letter isn't dated the report date",
    );
    expect(completionBlocker("going_concern_not_decided")).toBe("Going concern not decided");
  });

  it("the partner releases only after attesting (ac6)", async () => {
    const { calls } = page("engagement_partner", READY, {
      [`POST ${E}/completion/release`]: () =>
        json(
          {
            ...READY,
            release: {
              report_date: "2026-10-09",
              documentation_due: "2026-12-08",
              released_by_name: "Pat",
              at: "2026-10-09T15:07:00Z",
            },
            can_release: false,
            lock_blockers: [],
            can_lock: true,
          },
          201,
        ),
    });
    expect(await screen.findByText("Concurred · G6")).toBeTruthy();
    const button = screen.getByRole("button", { name: "Release report" });
    expect(button.hasAttribute("disabled")).toBe(true);
    fireEvent.click(
      screen.getByLabelText("I am the engagement partner and I authorize release of this report"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Release report" }));
    expect(await screen.findByText(/Documentation completion due 2026-12-08/)).toBeTruthy();
    expect(calls.find((c) => c.path.endsWith("/release"))?.body).toEqual({ attest: true });
  });

  it("a non-partner sees what blocks release and can't release (ac6)", async () => {
    page("senior", { ...READY, can_release: false, release_blockers: ["G7:no_rep_letter"] });
    expect(await screen.findByText("No signed representation letter")).toBeTruthy();
    expect(screen.getByText("Only the engagement partner can release this report.")).toBeTruthy();
  });

  it("the EQR concurs once notes are cleared, attesting independence (ac2)", async () => {
    const pending = {
      ...READY,
      eqr: { ...READY.eqr, is_me: true, concurrence: null, open_notes: 0 },
    };
    const { calls } = page("reviewer", pending, {
      [`POST ${E}/completion/eqr/concur`]: () => json(READY, 201),
    });
    fireEvent.click(
      await screen.findByLabelText("I was not involved in performing this engagement"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Concur" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/eqr/concur"))?.body).toEqual({
        not_involved: true,
      });
    });
  });

  it("shows the sealed archive (ac7)", async () => {
    page("manager", {
      ...READY,
      archive: {
        seal: "7c41" + "0".repeat(56) + "a9e2",
        leaf_count: 31,
        locked_by_name: "Hannah",
        at: "2026-12-03T22:18:00Z",
      },
    });
    expect(await screen.findByText(/seal 7c41…a9e2 · 31 items sealed/)).toBeTruthy();
  });
});
