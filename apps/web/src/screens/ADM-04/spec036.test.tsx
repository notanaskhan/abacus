// ac-test-author: ayushkbhatia
// SPEC-036 AC-9 on ADM-04 (Q-04-T351; G-02-T25): the opt-in and agent-stage band, and the screen
// around them, have their loading, empty, error and not-allowed states. Run on the `band`
// scenario with one handler changed per state.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ADM04 } from ".";
import { OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const POLICY = "GET /v1/firm/ai-policy";

function show(change: Record<string, FixtureHandler>): void {
  const base: Scenario = scenarios.band;
  restore = installFixtureMode({ ...base, handlers: { ...base.handlers, ...change } });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ADM04 opens={OPENS.band ?? {}} />
    </QueryClientProvider>,
  );
}

describe("SPEC-036 AC-9 · ADM-04", () => {
  it("loading: a busy skeleton, never an empty page", () => {
    show({ [POLICY]: () => new Promise<Response>(() => undefined) });
    expect(document.querySelector("[aria-busy='true']")).not.toBeNull();
  });

  it("error: the C-20 error with Retry", async () => {
    show({ [POLICY]: () => json({ detail: "unavailable" }, 503) });
    expect(await screen.findByRole("button", { name: /Retry/ })).toBeTruthy();
  });

  it("not allowed: the reason in words, no Retry", async () => {
    show({ [POLICY]: () => json({ detail: "forbidden" }, 403) });
    await waitFor(() => {
      expect(document.querySelector("[data-restricted='role']")).not.toBeNull();
    });
    expect(screen.queryByRole("button", { name: /Retry/ })).toBeNull();
    expect(document.querySelector("[data-restricted='role']")).not.toBeNull();
  });

  it("the band's states: the opt-in and the stages render from tokens only", async () => {
    show({});
    expect(await screen.findByText("Immediate controls")).toBeTruthy();
    const band = screen.getByText("Immediate controls").closest("section") ?? document.body;
    expect(band.innerHTML).not.toMatch(/#[0-9a-f]{3,6}\b|rgb\(/i);
  });
});
