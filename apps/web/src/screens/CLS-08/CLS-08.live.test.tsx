// C-02-T37 acceptance (TASK-8923; DEC-5925): "the studio button is absent in every live
// scenario". A production build folds PLANNED_VISIBLE to false; here it is held false and every
// CLS-08 artboard renders without the studio button, the Studio version row or Open letter.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { COPY as C } from "./copy";
import { CLS08 } from "./index";
import { CLS08_CLOSE_ID, type Cls08State, scenarios } from "./scenarios";

vi.mock("../../app-core/planned", () => ({ PLANNED_VISIBLE: false }));

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

describe("CLS-08 in a production build", () => {
  for (const state of Object.keys(scenarios) as Cls08State[]) {
    it(`CLS-08${state} acceptance: the studio button is absent`, async () => {
      restore = installFixtureMode(scenarios[state]);
      render(
        <QueryClientProvider client={newQueryClient()}>
          <CLS08 closeId={CLS08_CLOSE_ID} />
        </QueryClientProvider>,
      );
      await screen.findByText(C.basis.title);
      expect(screen.queryByRole("button", { name: C.studio.open })).toBeNull();
      expect(screen.queryByRole("button", { name: C.studio.view })).toBeNull();
      expect(screen.queryByText(C.release_band.studioVersion)).toBeNull();
      expect(document.querySelector("[data-planned-link]")).toBeNull();
      expect(screen.queryByText(C.basis.openLetter)).toBeNull();
    });
  }
});
