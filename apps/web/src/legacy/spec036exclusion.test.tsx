// ac-test-author: ayushkbhatia
// SPEC-036 AC-6 and AC-9 on the engagement-exclusion control (Q-04-T351): an excluded engagement
// says "AI is off for this engagement" to everyone on it; loading, error and not-allowed are
// states, never a blank. The ENG-02 mount is not built yet: SPEC-036 stays open naming it.
import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { AiExclusionControl } from "./AiClientData";

const E = "e1";
const ME = { user_id: "u-s", display_name: "Sam", memberships: [], active_tenant_id: "t1" };

function control(exclusion: () => Response | Promise<Response>, role = "staff"): void {
  mockApi({
    [`GET /v1/engagements/${E}/ai-exclusion`]: exclusion,
    [`GET /v1/engagements/${E}/team`]: () => json([{ user_id: "u-s", role }]),
    "GET /v1/me": () => json(ME),
  });
  renderRoutes([{ path: "/", component: () => <AiExclusionControl engagementId={E} /> }]);
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

describe("SPEC-036 AC-6 · the engagement says AI is off", () => {
  it("shows a staff member on the team that AI is off, with the partner's reason", async () => {
    control(() => json({ excluded: true, reason: "Client asked us not to", excluded_by: "u-p" }));
    expect(await screen.findByText("AI is off for this engagement")).toBeTruthy();
    expect(screen.getByText("Client asked us not to")).toBeTruthy();
  });
});

describe("SPEC-036 AC-9 · the control's states", () => {
  it("loading: a skeleton", () => {
    control(() => new Promise<Response>(() => undefined));
    expect(
      document.querySelector("[class*='skeleton'], [aria-busy='true'], .animate-pulse"),
    ).not.toBeNull();
  });

  it("error: says it couldn't load", async () => {
    control(() => json({ detail: "unavailable" }, 503));
    expect(await screen.findByText("Couldn't load this setting")).toBeTruthy();
  });

  it("not allowed: the reason in words", async () => {
    control(() => json({ detail: "forbidden" }, 403));
    await screen.findByText(/./);
    expect(document.querySelector("[data-restricted='role']")).not.toBeNull();
  });

  it("empty: nothing to say when AI is on and the viewer cannot switch it", async () => {
    control(() => json({ excluded: false, reason: null, excluded_by: null }));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("AI is off for this engagement")).toBeNull();
  });
});
