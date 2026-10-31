// KNW-04 C-20 states (K-02-T19; docs/screens/KNW-04.md non-artboard rows): loading keeps the
// frame and its section list, an error offers Try again and draws no rows, and a principal the
// matrix refuses (404) sees no standard and no count. Artboards a–j are KNW-04.test.tsx's,
// knw04-draft.test.tsx's and knw04-deadline.test.tsx's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { KNW04 } from ".";
import { COPY } from "./copy";
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

function show(over: Record<string, FixtureHandler>): void {
  const scenario = scenarios.a;
  restore = installFixtureMode({ ...scenario, handlers: { ...scenario.handlers, ...over } });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <KNW04 initial={OPENS.a} />
    </QueryClientProvider>,
  );
}

describe("KNW-04 C-20 states", () => {
  it("loading keeps the section list and marks the form busy", async () => {
    show({ "GET /v1/standards": () => new Promise<Response>(() => undefined) });
    expect(await screen.findByRole("navigation", { name: "Sections" })).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelector("[aria-busy='true']")).not.toBeNull();
    });
  });

  it("an error offers Try again and draws no rows", async () => {
    show({ "GET /v1/standards": () => json({ detail: "internal" }, 500) });
    expect(await screen.findByText(COPY.error)).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.retry })).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("a principal the matrix refuses (404) sees no standard and no count", async () => {
    show({
      "GET /v1/standards": () => json({ detail: "not_found" }, 404),
      "GET /v1/standards/{standard_id}": () => json({ detail: "not_found" }, 404),
    });
    expect(await screen.findByText(COPY.error)).toBeTruthy();
    expect(screen.queryByText("BH AJE thresholds v2")).toBeNull();
    expect(document.body.textContent).not.toMatch(/\d+ hidden/u);
  });
});
