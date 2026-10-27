// ac-test-author: ayushkbhatia
// P-03-T23 (TASK-1437; ADR-078): independent acceptance tests for the amber viewer UI, from
// SPEC-322 AC-26, AC-28, AC-31, AC-34 and P-03 §5.3, §5.6 only. Row acceptance: "After re-mask
// or unmount no copy of the revealed value or the password remains in the DOM, browser storage
// or React Query cache." Rendered from the SHL-08 fixture scenarios through the generated client
// (fixture mode answers at the network); the caches are the app's own QueryClient.
import { client } from "@abacus/api-client/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type Scenario, installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { SHL07 } from "../SHL-07/artboard";
import { scenarios as shl07 } from "../SHL-07/scenarios";
import { SHL08 } from "./artboard";
import { variant } from "../../fixtures/scenarios/SHL-08";
import { type Shl08State, scenarios } from "./scenarios";

// The SHL-08c fixture's box a value (P-03 §5.4) and the SHL-08d fixture password.
const VALUE = "000-00-6081";
const DIGITS = "6081";
const RIGHT = "fixture-password";
const WRONG = "Wr0ng-Sentinel-7Qx";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  vi.useRealTimers();
  cleanup();
  restore?.();
  restore = undefined;
  try {
    window.localStorage.clear();
    window.sessionStorage.clear();
  } catch {
    // storage may be unavailable; nothing to clear
  }
});

interface Mounted {
  queries: QueryClient;
  href: () => string;
  locationState: () => unknown;
  leave: () => void;
  unmount: () => void;
}

function mount(state: Shl08State, scenario: Scenario = scenarios[state]): Mounted {
  restore = installFixtureMode(scenario);
  const queries = newQueryClient();
  const root = createRootRoute({ component: Outlet });
  const router = createRouter({
    routeTree: root.addChildren([
      createRoute({
        getParentRoute: () => root,
        path: "/",
        component: () => <SHL08 state={state} />,
      }),
      createRoute({
        getParentRoute: () => root,
        path: "/elsewhere",
        component: () => <p>Another page</p>,
      }),
    ]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  const view = render(
    <QueryClientProvider client={queries}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return {
    queries,
    href: () => router.state.location.href,
    locationState: () => router.state.location.state,
    leave: () => {
      router.history.push("/elsewhere");
    },
    unmount: view.unmount,
  };
}

function storageText(): string {
  const read = (s: Storage): string =>
    Array.from({ length: s.length }, (_, i) => {
      const key = s.key(i) ?? "";
      return key + (s.getItem(key) ?? "");
    }).join("");
  try {
    return read(window.localStorage) + read(window.sessionStorage);
  } catch {
    return "";
  }
}

/** Everything the query and mutation caches hold: data, variables and errors. */
function cacheText(queries: QueryClient): string {
  return JSON.stringify([
    queries
      .getQueryCache()
      .getAll()
      .map((q) => [q.queryKey, q.state.data, String(q.state.error ?? "")]),
    queries
      .getMutationCache()
      .getAll()
      .map((m) => [m.options.mutationKey, m.state.data, m.state.variables, m.state.context]),
  ]);
}

/** The DOM as markup, attributes and input values included. */
function domText(): string {
  const values = Array.from(document.querySelectorAll("input, textarea")).map(
    (el) => (el as HTMLInputElement).value,
  );
  return document.documentElement.outerHTML + values.join(" ");
}

function nowhere(m: Mounted, secret: string): void {
  expect(domText()).not.toContain(secret);
  expect(cacheText(m.queries)).not.toContain(secret);
  expect(storageText()).not.toContain(secret);
  expect(window.location.href).not.toContain(secret);
  expect(m.href()).not.toContain(secret);
  expect(JSON.stringify(window.history.state ?? null)).not.toContain(secret);
  expect(JSON.stringify(m.locationState())).not.toContain(secret);
}

async function reveal(): Promise<void> {
  fireEvent.click(await screen.findByRole("button", { name: /^Reveal/ }));
  await waitFor(() => {
    expect(document.body.textContent).toContain(VALUE);
  });
}

describe("AC-26 MaskedValue lifecycle: the clear value lives in component memory only", () => {
  it("while shown, the value is in no cache, storage, URL or history entry", async () => {
    const m = mount("c");
    await reveal();
    expect(cacheText(m.queries)).not.toContain(DIGITS);
    expect(storageText()).not.toContain(DIGITS);
    expect(m.href()).not.toContain(DIGITS);
    expect(JSON.stringify(window.history.state ?? null)).not.toContain(DIGITS);
  });

  it("after Hide, no copy remains anywhere", async () => {
    const m = mount("c");
    await reveal();
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));
    nowhere(m, VALUE);
    expect(screen.getByText("Hidden again")).toBeTruthy();
  });

  it("after the 30 s window, no copy remains anywhere", async () => {
    const m = mount("c");
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await reveal();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    nowhere(m, VALUE);
  });

  it("is still shown at 29 s: the window is 30 s, not shorter", async () => {
    mount("c");
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await reveal();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(29_000);
    });
    expect(document.body.textContent).toContain(VALUE);
  });

  it("on route change, the value leaves with the viewer", async () => {
    const m = mount("c");
    await reveal();
    act(() => {
      m.leave();
    });
    await screen.findByText("Another page");
    nowhere(m, VALUE);
  });

  it("on unmount, no copy remains in the DOM, storage or the cache", async () => {
    const m = mount("c");
    await reveal();
    m.unmount();
    nowhere(m, VALUE);
  });
});

describe("AC-31, AC-34 the unlock form never echoes or stores the password", () => {
  async function submit(password: string): Promise<HTMLInputElement> {
    const field = await screen.findByLabelText<HTMLInputElement>("Password");
    expect(field.type).toBe("password");
    expect(field.getAttribute("autocomplete")).toBe("off");
    fireEvent.change(field, { target: { value: password } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
    return field;
  }

  it("a wrong password clears the field and leaves no copy anywhere", async () => {
    const m = mount("d");
    const field = await submit(WRONG);
    await screen.findByText("That password didn't open the file.");
    expect(field.value).toBe("");
    nowhere(m, WRONG);
  });

  it("the right password unlocks and leaves no copy anywhere", async () => {
    const m = mount("d");
    await submit(RIGHT);
    await waitFor(() => {
      expect(screen.queryByText("This PDF is password-protected.")).toBeNull();
    });
    nowhere(m, RIGHT);
  });

  it("after unmount, the typed but unsent password is gone too", async () => {
    const m = mount("d");
    const field = await screen.findByLabelText<HTMLInputElement>("Password");
    fireEvent.change(field, { target: { value: WRONG } });
    m.unmount();
    nowhere(m, WRONG);
  });

  it("the attempt limit answer shows the wait and never the password", async () => {
    const m = mount("d", variant("d", { unlockLimited: true }));
    await submit(WRONG);
    await screen.findByText(/Too many attempts/);
    nowhere(m, WRONG);
  });
});

describe("AC-28, AC-35 reveal and unlock are absent from agent surfaces", () => {
  const HUMAN_ONLY = /reveal|unlock|password/i;

  function controlsInAgentText(): string[] {
    return Array.from(document.querySelectorAll('[data-actor="agent"]')).flatMap((surface) =>
      Array.from(surface.querySelectorAll("button, input, a, [role='button']")).map(
        (el) => el.getAttribute("aria-label") ?? el.textContent,
      ),
    );
  }

  it.each(["a", "c", "d", "f"] as const)(
    "SHL-08%s: no control sits inside agent text",
    async (state) => {
      mount(state);
      await waitFor(() => {
        expect(document.querySelector("[data-page], [data-viewer-bar], input")).not.toBeNull();
      });
      expect(controlsInAgentText()).toEqual([]);
      for (const surface of Array.from(document.querySelectorAll('[data-actor="agent"]')))
        expect(surface.textContent).not.toMatch(/Reveal \(logged\)|Unlock/);
    },
  );

  it("the dock's Agent pane offers neither Reveal nor Unlock", async () => {
    mount("b");
    const agentTab = await screen
      .findByRole("radio", { name: "Agent" })
      .catch(() => screen.findByRole("button", { name: "Agent" }));
    fireEvent.click(agentTab);
    const named = screen
      .queryAllByRole("button")
      .map((b) => b.getAttribute("aria-label") ?? b.textContent);
    expect(named.filter((n) => HUMAN_ONLY.test(n))).toEqual([]);
    expect(screen.queryByLabelText("Password")).toBeNull();
  });

  it.each(["a", "b", "c", "d", "e"] as const)(
    "SHL-07%s: the citation popover, an agent's citations, offers neither",
    async (state) => {
      restore = installFixtureMode(shl07[state]);
      const queries = newQueryClient();
      const root = createRootRoute({ component: Outlet });
      const router = createRouter({
        routeTree: root.addChildren([
          createRoute({
            getParentRoute: () => root,
            path: "/",
            component: () => <SHL07 state={state} />,
          }),
        ]),
        history: createMemoryHistory({ initialEntries: ["/"] }),
      });
      render(
        <QueryClientProvider client={queries}>
          <RouterProvider router={router} />
        </QueryClientProvider>,
      );
      await waitFor(() => {
        expect(document.querySelector('[data-cite="card"], [role="dialog"]')).not.toBeNull();
      });
      const dialogs = screen.queryAllByRole("dialog");
      for (const d of dialogs) {
        const names = within(d)
          .queryAllByRole("button")
          .map((b) => b.getAttribute("aria-label") ?? b.textContent);
        expect(names.filter((n) => HUMAN_ONLY.test(n))).toEqual([]);
      }
      expect(controlsInAgentText()).toEqual([]);
    },
  );
});
