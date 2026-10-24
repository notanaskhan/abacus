// SHL-08 fixture artboards (P-03-T07): every state P-03 builds (a–f, h) renders from its scenario
// through the generated client, on the E5 shell until P-03-T14's EvidenceViewer.
import { client } from "@abacus/api-client/client";
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { SHL08 } from "./artboard";
import { STATES, type Shl08State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Shl08State): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([{ path: "/", component: () => <SHL08 state={state} /> }]);
}

const NAMES: Partial<Record<Shl08State, string>> = {
  a: "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
  b: "Harborline Net Trust Assets 12-31-2025.pdf",
  c: "2025 W-2 From Mercer Hill Health [Claire].pdf",
  d: "Halvard_2025_Consolidated_1099.pdf",
  f: "Ridgeline 2025 K-1 statement.pdf",
  h: "Harborline Net Trust Assets 12-31-2025.pdf",
};

describe("SHL-08 fixture artboards", () => {
  it("cover a–f and h", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "h"]);
  });

  for (const state of STATES) {
    it(`${state}: renders from its fixtures`, async () => {
      show(state);
      const frame = await screen.findByText((_, el) => el?.getAttribute("data-state") === state);
      expect(frame.getAttribute("data-screen")).toBe("SHL-08");
      const name = NAMES[state];
      if (name !== undefined) {
        await waitFor(() => {
          expect(document.body.textContent).toContain(name);
        });
      }
    });
  }

  it("c: the SSN stays masked as its token", async () => {
    show("c");
    await waitFor(() => {
      expect(document.body.textContent).toContain("•••-••-6081");
    });
    expect(document.body.textContent).not.toContain("000-00-6081");
  });
});
