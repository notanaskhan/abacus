// ADM-01 · Settings home & firm profile (G-01-T07). One test per artboard (a–f) on its fixture
// scenario (G-01 AC1.1–AC1.10, AC2.1–AC2.2): the clean form, a dirty change, the required display
// name, the partner's and the security admin's read-only views, the save and its toast, the
// leave guard, and the not-allowed answer for someone without a settings role.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ADM01 } from ".";
import { type Adm01State, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(state: Adm01State, scenario: Scenario = scenarios[state], onNavigate = vi.fn()) {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ADM01 onNavigate={onNavigate} />
    </QueryClientProvider>,
  );
  return { seen, onNavigate };
}

function save(): HTMLButtonElement {
  return screen.getByRole("button", { name: "Save" });
}

describe("ADM-01 artboards", () => {
  it("has a scenario for every artboard a–f", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
    expect(scenarios.d.persona).toBe("daniel-reyes");
    expect(scenarios.e.persona).toBe("felix-andersen");
    for (const s of STATES) expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
  });

  it("ADM-01a clean: the frame, the profile, offices foot to 46 and At a glance", async () => {
    show("a");
    expect(await screen.findByText("Brightwater Hale LLP")).toBeTruthy();
    expect(await screen.findByText("Firm profile")).toBeTruthy();
    expect(screen.getByText("United States")).toBeTruthy();
    expect(await screen.findByText("Chicago · HQ")).toBeTruthy();
    expect(screen.getByText("22 seats · 98 TY2025 returns")).toBeTruthy();
    expect(screen.getByText("46 seats · 224 returns")).toBeTruthy();
    expect(await screen.findByText("46 of 46 used")).toBeTruthy();
    expect(
      screen.getByText("All seats are assigned. Add seats before inviting another user."),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "7 partners · 37 professional staff · 8 operations; 6 back-office staff hold no seat",
      ),
    ).toBeTruthy();
    expect(screen.getByText("46 of 46 seats · 0 pending invites")).toBeTruthy();
    expect(screen.getByText("3 offices · 4 teams · 3 ethical walls")).toBeTruthy();
    expect(screen.getByText("Updated 9:24 AM")).toBeTruthy();
    const glance = screen.getByRole("region", { name: "At a glance" });
    expect(within(glance).getAllByRole("button")).toHaveLength(11);
    expect(save().disabled).toBe(true);
    expect(screen.queryByText("Unsaved changes")).toBeNull();
  });

  it("ADM-01b dirty: Eastern Time makes the form unsaved and Save enabled", async () => {
    show("b");
    const zone = await screen.findByRole("button", {
      name: "Default time zone: Central Time (CT)",
    });
    zone.focus();
    fireEvent.keyDown(zone, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "Eastern Time (ET)" }));
    expect(await screen.findByText("Unsaved changes")).toBeTruthy();
    expect(save().disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.queryByText("Unsaved changes")).toBeNull();
  });

  it("ADM-01c validation: an empty display name reads Required and blocks Save", async () => {
    show("c");
    const field = await screen.findByDisplayValue("Brightwater Hale");
    fireEvent.change(field, { target: { value: "" } });
    expect(await screen.findByText("Enter the name clients see in the portal.")).toBeTruthy();
    expect(save().disabled).toBe(true);
  });

  it("ADM-01d partner: the banner, locks, no Save, At a glance visible", async () => {
    show("d");
    expect(await screen.findByText("Only firm admins can edit these settings.")).toBeTruthy();
    expect(await screen.findByText("Firm profile")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.getAllByRole("img", { name: "Locked" }).length).toBeGreaterThanOrEqual(4);
    expect(await screen.findByText("46 of 46 used")).toBeTruthy();
    expect(screen.getByRole("region", { name: "At a glance" })).toBeTruthy();
  });

  it("ADM-01e security admin: read-only, no Plan & seats, Security first", async () => {
    const { seen } = show("e");
    expect(await screen.findByText("Only firm admins can edit these settings.")).toBeTruthy();
    expect(await screen.findByText("Firm profile")).toBeTruthy();
    expect(screen.queryByText("Plan & seats")).toBeNull();
    expect(seen.calls.some((c) => c.path === "/v1/firm/settings/plan")).toBe(false);
    const glance = screen.getByRole("region", { name: "At a glance" });
    expect(within(glance).getAllByRole("button")[0]?.textContent).toContain("Security");
  });

  it("ADM-01f saved: the PATCH carries the version, then the toast", async () => {
    const { seen } = show("f");
    const zone = await screen.findByRole("button", {
      name: "Default time zone: Central Time (CT)",
    });
    zone.focus();
    fireEvent.keyDown(zone, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "Eastern Time (ET)" }));
    fireEvent.click(save());
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain("Firm settings saved");
    });
    const patch = seen.calls.find((c) => c.method === "PATCH");
    expect(patch?.path).toBe("/v1/firm/settings/profile");
    expect(patch?.body).toEqual({ version: 1, values: { time_zone: "America/New_York" } });
    await waitFor(() => {
      expect(screen.queryByText("Unsaved changes")).toBeNull();
    });
  });

  it("asks Discard changes? before leaving a dirty form (AC1.10)", async () => {
    const { onNavigate } = show("b");
    const zone = await screen.findByRole("button", {
      name: "Default time zone: Central Time (CT)",
    });
    zone.focus();
    fireEvent.keyDown(zone, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "Eastern Time (ET)" }));
    fireEvent.click(await screen.findByText("46 of 46 seats · 0 pending invites"));
    expect(await screen.findByText("Discard changes?")).toBeTruthy();
    expect(onNavigate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(onNavigate).toHaveBeenCalledWith("people");
  });

  it("answers not-allowed to someone without a settings role (AC1.8)", async () => {
    const base = scenarios.a;
    show("a", {
      ...base,
      persona: "kevin-osei",
      handlers: {
        ...base.handlers,
        "GET /v1/firm/settings/overview": () => json({ detail: "not found" }, 404),
      },
    });
    expect(await screen.findByText("You don't have access to firm settings.")).toBeTruthy();
  });
});
