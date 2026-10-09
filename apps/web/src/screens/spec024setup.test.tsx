// SPEC-024 (TASK-042): the onboarding checklist and the autonomy policy.
import type { OnboardingOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Autonomy } from "./Autonomy";
import { Onboarding } from "./Onboarding";

function state(done: string[], over: Partial<OnboardingOut> = {}): OnboardingOut {
  const ids = ["sso", "team", "methodology", "autonomy", "budget", "walls", "engagement"] as const;
  return {
    steps: ids.map((id) => ({ id, done: done.includes(id), how: null })),
    dismissed: false,
    complete: done.length === ids.length,
    ...over,
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

describe("ac7 onboarding checklist", () => {
  it("shows progress and each step, links the ones to do, and skips SSO for now", async () => {
    const { calls } = mockApi({
      "GET /v1/firm/onboarding": () => json(state(["methodology", "engagement"])),
      "POST /v1/firm/onboarding/sso/acknowledge": () =>
        json(state(["sso", "methodology", "engagement"])),
    });
    renderRoutes([{ path: "/", component: () => <Onboarding /> }]);
    expect(await screen.findByText("2 of 7 done")).toBeTruthy();
    const steps = screen.getByRole("list", { name: "Setup steps" });
    expect(within(steps).getAllByRole("listitem")).toHaveLength(7);
    expect(within(steps).getByText(/Upload your methodology/).textContent).toContain("(done)");
    expect(within(steps).getByRole("link", { name: "Invite people" }).getAttribute("href")).toBe(
      "/admin/people",
    );
    fireEvent.click(within(steps).getByRole("button", { name: "Skip for now" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path === "/v1/firm/onboarding/sso/acknowledge")).toBe(true);
    });
  });

  it("disappears when every step is done or it was dismissed, and shows nothing to others", async () => {
    mockApi({ "GET /v1/firm/onboarding": () => json(state([], { dismissed: true })) });
    renderRoutes([{ path: "/", component: () => <Onboarding /> }]);
    await waitFor(() => {
      expect(screen.queryByText("Get your firm ready")).toBeNull();
    });
    cleanup();
    mockApi({ "GET /v1/firm/onboarding": () => json({ detail: "forbidden" }, 403) });
    renderRoutes([{ path: "/", component: () => <Onboarding /> }]);
    await waitFor(() => {
      expect(screen.queryByText("Get your firm ready")).toBeNull();
    });
  });
});

describe("ac5 autonomy", () => {
  it("offers Advise and Routine, marks Manage and Portfolio as coming, and confirms Routine", async () => {
    const { calls } = mockApi({
      "GET /v1/firm/autonomy": () => json({ level: 1, set_at: null }),
      "PUT /v1/firm/autonomy": () => json({ level: 1, set_at: "2026-10-09T12:00:00Z" }),
    });
    renderRoutes([{ path: "/", component: () => <Autonomy canSet /> }]);
    const manage = await screen.findByRole("radio", { name: /Manage/ });
    expect((manage as HTMLInputElement).disabled).toBe(true);
    expect(screen.getAllByText("Coming with the engagement agent")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Confirm Routine" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ level: 1 });
    });
  });

  it("lets an administrator choose Advise, and shows practice leaders the level read-only", async () => {
    const { calls } = mockApi({
      "GET /v1/firm/autonomy": () => json({ level: 1, set_at: "2026-10-09T12:00:00Z" }),
      "PUT /v1/firm/autonomy": () => json({ level: 0, set_at: "2026-10-09T12:05:00Z" }),
    });
    renderRoutes([{ path: "/", component: () => <Autonomy canSet /> }]);
    fireEvent.click(await screen.findByRole("radio", { name: /Advise/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ level: 0 });
    });
    cleanup();
    mockApi({ "GET /v1/firm/autonomy": () => json({ level: 1, set_at: null }) });
    renderRoutes([{ path: "/", component: () => <Autonomy canSet={false} /> }]);
    expect(await screen.findByText("Only firm administrators can change this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Save|Confirm/ })).toBeNull();
  });
});
