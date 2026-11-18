// G-04-T14 (TASK-8548; DEC-5532): the console's staff auth client. The access token lives in
// memory only (never web storage), refreshes run one at a time with the CSRF header, a refused
// refresh keeps the BFF's reason, and the callback landing names a same-origin path or a refusal.
import { client } from "@abacus/api-client/client";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode, json } from "../app-core/fixture-mode";
import { callbackOf } from "./ConsoleShell";
import { consoleToken, lastConsoleFailure, refreshConsoleSession, resetConsoleAuth } from "./auth";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  restore?.();
  restore = undefined;
  resetConsoleAuth();
  sessionStorage.clear();
  localStorage.clear();
});

describe("console auth client", () => {
  it("holds the token in memory, one refresh at a time, with the CSRF header", async () => {
    let calls = 0;
    let csrf: string | null = null;
    restore = installFixtureMode({
      state: "live",
      handlers: {
        "POST /v1/platform/auth/refresh": ({ headers }) => {
          calls += 1;
          csrf = headers?.get("X-Abacus-CSRF") ?? null;
          return json({ access_token: "staff-token", expires_in: 600 });
        },
      },
    });
    const [a, b] = await Promise.all([refreshConsoleSession(0), refreshConsoleSession(0)]);
    expect([a, b, calls, csrf]).toEqual([true, true, 1, "1"]);
    expect(consoleToken(0)).toBe("staff-token");
    expect(consoleToken(600_000)).toBeNull(); // past expiry less the margin
    const stored = [sessionStorage, localStorage].flatMap((store) =>
      Array.from({ length: store.length }, (_, i) => store.getItem(store.key(i) ?? "") ?? ""),
    );
    expect(stored.join(" ")).not.toContain("staff-token");
  });

  it("a refused refresh keeps the BFF's reason and holds no token", async () => {
    restore = installFixtureMode({
      state: "live",
      handlers: {
        "POST /v1/platform/auth/refresh": () => json({ detail: "session_refresh_reused" }, 401),
      },
    });
    expect(await refreshConsoleSession(0)).toBe(false);
    expect(lastConsoleFailure()).toBe("session_refresh_reused");
    expect(consoleToken(0)).toBeNull();
  });
});

describe("the callback landing", () => {
  it("names a same-origin path, a refusal, or nothing off the callback page", () => {
    expect(callbackOf("/signin/callback", "?to=%2Ftenants")).toEqual({ to: "/tenants" });
    expect(callbackOf("/signin/callback", "?to=%2F%2Fevil.test")).toEqual({ to: "/" });
    expect(callbackOf("/signin/callback", "?error=no_console_role")).toEqual({
      error: "no_console_role",
    });
    expect(callbackOf("/tenants", "?to=%2Fx")).toBeNull();
  });
});
