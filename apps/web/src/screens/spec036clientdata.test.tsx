// SPEC-036 AC-3, AC-6, AC-9 (TASK-076): a firm admin opts in against the disclosure; assistants
// show their stage; an engagement partner switches AI off for one engagement.
import type { AiClientDataOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { AiClientDataSetting, AiExclusionControl } from "./AiClientData";

const E = "e1";
const ME = { user_id: "u-p", display_name: "Pat", memberships: [], active_tenant_id: "t1" };
const OFF: AiClientDataOut = {
  available: true,
  current: false,
  lapsed: false,
  disclosure: {
    provider: "Amazon Web Services",
    region: "us-east-1",
    retention_exceptions: [],
    subprocessors: [],
    review_by: "2027-09-30",
    letter_wording: "We use AI assistants…",
  },
  assistants: [{ agent_id: "evidence.screener", purpose: "Screen evidence", stage: "shadow" }],
};

function setting(data: AiClientDataOut | (() => Response), extra = {}) {
  const api = mockApi({
    "GET /v1/firm/ai-client-data": typeof data === "function" ? data : () => json(data),
    ...extra,
  });
  renderRoutes([{ path: "/", component: () => <AiClientDataSetting canSet /> }]);
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

describe("ac3 opting in", () => {
  it("opts in only after confirming the disclosure was read", async () => {
    const { calls } = setting(OFF, {
      "PUT /v1/firm/ai-client-data": () => json({ ...OFF, current: true }),
    });
    expect(await screen.findByText(/Amazon Web Services, in our own account/)).toBeTruthy();
    expect(screen.getByText("Trial (not shown to your team yet)")).toBeTruthy();
    const turnOn = screen.getByRole("button", { name: "Turn on" });
    expect((turnOn as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/I've read how our clients' data is handled/));
    fireEvent.click(turnOn);
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ on: true });
    });
    expect(await screen.findByRole("button", { name: "Turn off" })).toBeTruthy();
  });

  it("says when the terms changed", async () => {
    setting({ ...OFF, lapsed: true });
    expect(await screen.findByText("The terms changed")).toBeTruthy();
  });
});

describe("ac9 states", () => {
  it("says it isn't available yet without terms", async () => {
    setting({ ...OFF, available: false, disclosure: null, assistants: [] });
    expect(await screen.findByText(/Not available yet/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Turn on" })).toBeNull();
  });

  it("explains the setting is for firm administrators", async () => {
    setting(() => json({ detail: "forbidden" }, 403));
    expect(await screen.findByText(/Only firm administrators/)).toBeTruthy();
  });

  it("shows an error when it can't load", async () => {
    setting(() => json({ detail: "boom" }, 500));
    expect(await screen.findByText("Couldn't load this setting")).toBeTruthy();
  });
});

describe("ac6 engagement exclusion", () => {
  function control(excluded: boolean, role: string, extra = {}) {
    let state = { excluded, reason: excluded ? "Client asked" : null };
    const api = mockApi({
      "GET /v1/me": () => json(ME),
      [`GET /v1/engagements/${E}/team`]: () =>
        json([{ user_id: "u-p", display_name: "Pat", role }]),
      [`GET /v1/engagements/${E}/ai-exclusion`]: () => json(state),
      [`PUT /v1/engagements/${E}/ai-exclusion`]: () => {
        state = { excluded: true, reason: "Client asked" };
        return json(state);
      },
      ...extra,
    });
    renderRoutes([{ path: "/", component: () => <AiExclusionControl engagementId={E} /> }]);
    return api;
  }

  it("lets the partner switch AI off with a reason", async () => {
    const { calls } = control(false, "engagement_partner");
    fireEvent.click(
      await screen.findByRole("button", { name: "Turn AI off for this engagement" }),
    );
    fireEvent.change(screen.getByLabelText(/Why/), { target: { value: "Client asked" } });
    fireEvent.click(screen.getByRole("button", { name: "Turn off" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        excluded: true,
        reason: "Client asked",
      });
    });
    expect(await screen.findByText("AI is off for this engagement")).toBeTruthy();
  });

  it("shows everyone that AI is off, but only the partner can switch it", async () => {
    control(true, "senior");
    expect(await screen.findByText("AI is off for this engagement")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Turn AI back on" })).toBeNull();
  });
});
