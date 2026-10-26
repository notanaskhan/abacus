// A-02-T14 (TASK-1338): with the planned controls folded away, as a production build does
// (app-core/planned.ts), AUD-06g and h draw no entity strip and no Hand off to tax….
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { AUD06Frame } from "./artboard";
import { type Aud06State, scenarios } from "./scenarios";

vi.mock("../../app-core/planned", () => ({ PLANNED_VISIBLE: false }));

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

describe("AUD-06 in a production build (A-02-T14)", () => {
  for (const state of ["g", "h"] as const satisfies readonly Aud06State[]) {
    it(`AUD-06${state} draws neither the entity strip nor Hand off to tax`, async () => {
      restore = installFixtureMode(scenarios[state]);
      render(
        <QueryClientProvider client={newQueryClient()}>
          <AUD06Frame state={state} />
        </QueryClientProvider>,
      );
      await waitFor(
        () => {
          expect(document.querySelector("[data-aud06='lines']")).not.toBeNull();
        },
        { timeout: 4000 },
      );
      expect(document.querySelector("[data-aud06='entities']")).toBeNull();
      expect(document.querySelector("[data-aud06='hand-off']")).toBeNull();
      expect(document.body.textContent).not.toContain("Hand off to tax");
    });
  }
});
