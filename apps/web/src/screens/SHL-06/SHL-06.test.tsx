// SHL-06 · Firm sign-in (P-01-T11): g on its fixture scenario and the sign-in error state, against
// P-01 AC 5.1.3 (spinner, refresh, /v1/me, the safe return path) and AC 5.1.5 (no token in web
// storage). a–f are the hosted provider's and are not built here.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { type Scenario, installFixtureMode } from "../../app-core/fixture-mode";
import { accessToken, resetAuthForTest } from "../../app-core/auth";
import { configureClient } from "../../api";
import { stubLocation, withQueries } from "../../testing/support";
import { SHL06 } from ".";
import { SEARCH, STATES, type Shl06State, scenarios } from "./scenarios";

beforeAll(() => {
  configureClient();
});

let restore: (() => void) | undefined;
let assign: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetAuthForTest();
  sessionStorage.clear();
  localStorage.clear();
  assign = stubLocation("/signin/callback").assign;
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  vi.unstubAllGlobals();
  resetAuthForTest();
});

interface Seen {
  calls: { method: string; path: string; csrf: string | null; auth: string | null }[];
}

function show(
  state: Shl06State,
  search: string = SEARCH[state],
  scenario: Scenario = scenarios[state],
): { seen: Seen; onDone: ReturnType<typeof vi.fn> } {
  const seen: Seen = { calls: [] };
  restore = installFixtureMode(scenario);
  // Record what reached the network, headers included, beneath fixture mode.
  const fixtureFetch = client.getConfig().fetch;
  client.setConfig({
    fetch: (input: RequestInfo | URL) => {
      // The generated client always hands fetch a Request.
      const request = input as Request;
      seen.calls.push({
        method: request.method,
        path: new URL(request.url).pathname,
        csrf: request.headers.get("x-abacus-csrf"),
        auth: request.headers.get("authorization"),
      });
      if (fixtureFetch === undefined) throw new Error("fixture mode is not installed");
      return fixtureFetch(request);
    },
  });
  const onDone = vi.fn();
  withQueries(<SHL06 search={search} onDone={onDone} />);
  return { seen, onDone };
}

/** Every value in web storage (AC 5.1.5). */
function webStorage(): string {
  const all: string[] = [];
  for (const store of [sessionStorage, localStorage]) {
    for (let i = 0; i < store.length; i++) {
      const key = store.key(i);
      if (key !== null) all.push(`${key}=${store.getItem(key) ?? ""}`);
    }
  }
  return all.join("\n");
}

describe("SHL-06 artboards", () => {
  it("defines g and the sign-in error states, as Hannah Leclerc at E0", () => {
    expect(STATES).toEqual(["g", "error", "expired"]);
    for (const s of STATES) {
      expect(scenarios[s].persona).toBe("hannah-leclerc");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
  });

  it("SHL-06g signing in", async () => {
    const { seen, onDone } = show("g");
    expect(screen.getByRole("heading", { name: "Sign in to Accrued" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Accrued" })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toBe("Signing in…");
    expect(screen.getByRole("button", { name: "Signing in…" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(screen.getByText("System status")).toBeTruthy();
    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith("/engagements");
    });
    // AC 5.1.3: the refresh with the CSRF header, then /v1/me with the in-memory token.
    expect(seen.calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      "POST /v1/auth/refresh",
      "GET /v1/me",
    ]);
    expect(seen.calls[0]?.csrf).toBe("1");
    expect(seen.calls[1]?.auth).toBe("Bearer fixture-session");
    expect(accessToken()).toBe("fixture-session");
  });

  it("SHL-06g keeps no token in web storage (AC 5.1.5)", async () => {
    const { onDone } = show("g");
    await waitFor(() => {
      expect(onDone).toHaveBeenCalled();
    });
    expect(webStorage()).not.toContain("fixture-session");
  });

  it("SHL-06g opens only a same-origin return path", async () => {
    const { onDone } = show("g", "?to=https%3A%2F%2Fevil.example%2F");
    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith("/");
    });
  });

  it("SHL-06g returns to the route the session expired on, query included", async () => {
    const { onDone } = show("g", "?to=%2Fbinders%3Fseason%3DTY2025");
    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith("/binders?season=TY2025");
    });
  });

  it("SHL-06 error: the BFF refused for want of a second factor", () => {
    const { seen, onDone } = show("error");
    expect(screen.getByRole("heading", { name: "Sign-in didn't complete" })).toBeTruthy();
    expect(
      screen.getByText(
        "Your sign-in needs a second factor. Turn on two-step verification with your sign-in provider, then sign in again.",
      ),
    ).toBeTruthy();
    // A refused landing never asks the BFF for a token.
    expect(seen.calls).toEqual([]);
    expect(onDone).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(assign).toHaveBeenCalledWith("/v1/auth/sign-in?return_to=%2F");
  });

  it("SHL-06 error: an unknown code reads as the generic failure", () => {
    show("error", "?error=%3Cscript%3E");
    expect(screen.getByText("The response from the sign-in page couldn't be used.")).toBeTruthy();
    expect(screen.queryByText("<script>")).toBeNull();
  });

  it("SHL-06 expired: no live session, so sign in again to the same route", async () => {
    const { onDone } = show("expired");
    expect(await screen.findByText("Your session ended. Sign in again to carry on.")).toBeTruthy();
    expect(onDone).not.toHaveBeenCalled();
    expect(accessToken()).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(assign).toHaveBeenCalledWith("/v1/auth/sign-in?return_to=%2Fengagements");
  });

  it("SHL-06 never names the provider's methods or asks for a password", () => {
    show("error");
    expect(document.querySelector("input[type=password]")).toBeNull();
    expect(screen.queryByText(/password/i)).toBeNull();
  });
});
