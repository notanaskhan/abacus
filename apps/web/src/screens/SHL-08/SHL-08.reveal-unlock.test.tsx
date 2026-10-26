// P-03-T20: SHL-08 masked PII (c), password-locked (d) and in-document search, from the fixture
// scenarios through the generated client. Row acceptance: "The clear value lives only in
// component memory for 30 seconds and is never cached, persisted or put in the URL, and Ask Jonah
// & Claire Feld... opens SHL-14 prefilled." Plus P-03 AC4.4–AC4.6, AC5.1, AC5.3, AC5.4, AC3.9.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type Scenario, installFixtureMode } from "../../app-core/fixture-mode";
import { variant } from "../../fixtures/scenarios/SHL-08";
import { newQueryClient, renderRoutes } from "../../testing/support";
import { SHL08 } from "./artboard";
import { scenarios } from "./scenarios";

const VALUE = "000-00-6081";
const LINE = "Revealed by Samuel Ito · 9:31 AM · logged to the audit trail";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  vi.useRealTimers();
  cleanup();
  restore?.();
  restore = undefined;
});

function show(scenario: Scenario, state: "c" | "d" | "h"): void {
  restore = installFixtureMode(scenario);
  renderRoutes([{ path: "/", component: () => <SHL08 state={state} /> }]);
}

function storageText(): string {
  const read = (s: Storage): string =>
    Array.from({ length: s.length }, (_, i) => s.getItem(s.key(i) ?? "") ?? "").join("");
  try {
    return read(window.localStorage) + read(window.sessionStorage);
  } catch {
    return "";
  }
}

describe("SHL-08c masked PII and the logged reveal", () => {
  it("reveals for 30 seconds with the logged line, then re-masks; nothing is cached or kept", async () => {
    const queries = newQueryClient();
    restore = installFixtureMode(scenarios.c);
    const root = createRootRoute({ component: Outlet });
    const router = createRouter({
      routeTree: root.addChildren([
        createRoute({
          getParentRoute: () => root,
          path: "/",
          component: () => <SHL08 state="c" />,
        }),
      ]),
      history: createMemoryHistory({ initialEntries: ["/"] }),
    });
    render(
      <QueryClientProvider client={queries}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    const chip = await screen.findByRole("button", { name: "Reveal (logged)" });
    expect(document.body.textContent).toContain("•••-••-6081");
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fireEvent.click(chip);
    await waitFor(() => {
      expect(document.body.textContent).toContain(VALUE);
    });
    expect(document.body.textContent).toContain(LINE);
    expect(screen.getByRole("button", { name: "Hide" })).toBeTruthy();
    expect(screen.getByText("Revealed for 30 seconds")).toBeTruthy();
    // Never in the query or mutation caches, browser storage or the URL.
    const cached = JSON.stringify([
      queries
        .getQueryCache()
        .getAll()
        .map((q) => q.state.data),
      queries
        .getMutationCache()
        .getAll()
        .map((m) => m.state.data),
    ]);
    expect(cached).not.toContain(VALUE);
    expect(storageText()).not.toContain(VALUE);
    expect(window.location.href).not.toContain("6081");
    expect(router.state.location.href).not.toContain("6081");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(document.body.textContent).not.toContain(VALUE);
    expect(document.body.textContent).not.toContain(LINE);
    expect(screen.getByText("Hidden again")).toBeTruthy();
  });

  it("Hide re-masks at once", async () => {
    show(scenarios.c, "c");
    fireEvent.click(await screen.findByRole("button", { name: "Reveal (logged)" }));
    fireEvent.click(await screen.findByRole("button", { name: "Hide" }));
    expect(document.body.textContent).not.toContain(VALUE);
    expect(screen.getByRole("button", { name: "Reveal (logged)" })).toBeTruthy();
  });

  it("a stale MFA opens the step-up and reveals nothing", async () => {
    show(variant("c", { revealNeedsMfa: true }), "c");
    fireEvent.click(await screen.findByRole("button", { name: "Reveal (logged)" }));
    expect(await screen.findByText("Confirm it's you")).toBeTruthy();
    expect(document.body.textContent).not.toContain(VALUE);
  });

  it("the value leaves with the viewer", async () => {
    show(scenarios.c, "c");
    fireEvent.click(await screen.findByRole("button", { name: "Reveal (logged)" }));
    await waitFor(() => {
      expect(document.body.textContent).toContain(VALUE);
    });
    cleanup();
    expect(document.body.textContent).not.toContain(VALUE);
  });
});

describe("SHL-08d password-locked", () => {
  it("shows the lock, the field, Unlock and Ask …", async () => {
    show(scenarios.d, "d");
    expect(await screen.findByText("This PDF is password-protected.")).toBeTruthy();
    expect(
      screen.getByText("Enter the password Halvard sent the client, or ask the client for it."),
    ).toBeTruthy();
    const field = screen.getByLabelText<HTMLInputElement>("Password");
    expect(field.type).toBe("password");
    expect(field.getAttribute("autocomplete")).toBe("off");
    expect(screen.getByRole("button", { name: "Unlock" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ask Jonah & Claire Feld…" })).toBeTruthy();
  });

  it("a wrong password says so, tied to the field, and the field is cleared", async () => {
    show(scenarios.d, "d");
    const field = await screen.findByLabelText<HTMLInputElement>("Password");
    fireEvent.change(field, { target: { value: "not-it" } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
    expect(field.value).toBe("");
    const error = await screen.findByText("That password didn't open the file.");
    expect(field.getAttribute("aria-describedby")).toBe(error.id);
    expect(document.body.textContent).not.toContain("not-it");
  });

  it("the right password shows the derivation's masked pages", async () => {
    show(scenarios.d, "d");
    const field = await screen.findByLabelText<HTMLInputElement>("Password");
    fireEvent.change(field, { target: { value: "fixture-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
    await waitFor(() => {
      expect(screen.queryByText("This PDF is password-protected.")).toBeNull();
    });
    expect(document.body.textContent).not.toContain("fixture-password");
  });

  it("the attempt limit gives the wait", async () => {
    show(variant("d", { unlockLimited: true }), "d");
    const field = await screen.findByLabelText<HTMLInputElement>("Password");
    fireEvent.change(field, { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
    expect(await screen.findByText("Too many attempts. Try again in 10 minutes.")).toBeTruthy();
  });

  it("flag off: Ask … only", async () => {
    show(variant("d", { unlockOff: true }), "d");
    expect(await screen.findByText("This PDF is password-protected.")).toBeTruthy();
    expect(screen.queryByLabelText("Password")).toBeNull();
    expect(screen.queryByRole("button", { name: "Unlock" })).toBeNull();
    expect(screen.getByRole("button", { name: "Ask Jonah & Claire Feld…" })).toBeTruthy();
  });
});

describe("SHL-08 in-document search", () => {
  it("asks the server and reports its hits", async () => {
    show(scenarios.h, "h");
    fireEvent.click(await screen.findByRole("button", { name: "Find in document" }));
    const input = screen.getByRole("textbox", { name: "Find in document" });
    fireEvent.change(input, { target: { value: "2,915,330" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("1 match")).toBeTruthy();
  });
});
