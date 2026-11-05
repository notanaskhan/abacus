// A-06-T24 (TASK-3320): AUD-17 in fixture mode. Row: "Every AUD-17 artboard renders from its scenario,
// chips open SHL-12 and never sign, and the legend states that a review note blocks sign-off and a
// comment never does."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { AUD17_ENGAGEMENT, AUD17_WORK_ITEM } from "../../fixtures/seed/aud17";
import { newQueryClient } from "../../testing/support";
import { ReviewNotesPane } from "./Notes";
import { type Aud17State, scenarios, STATES } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Aud17State): ReturnType<typeof vi.fn> {
  const onSignOff = vi.fn();
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ReviewNotesPane
        engagementId={AUD17_ENGAGEMENT}
        workItemId={AUD17_WORK_ITEM}
        onSignOff={onSignOff}
      />
    </QueryClientProvider>,
  );
  return onSignOff;
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

describe("AUD-17", () => {
  it("has a scenario for every artboard", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("a: the server's footer and the legend", async () => {
    show("a");
    expect((await drawn("[data-aud17='footer']")).textContent).toContain(
      "Partner 8 of 13 · EQR 0 of 6 · Changed after sign-off 1",
    );
    expect((await drawn("[data-aud17='legend']")).textContent).toContain(
      "a review note blocks sign-off; a comment never does",
    );
  });

  it("chips open SHL-12 and never sign: an empty L4 and a signed chip only call back", async () => {
    const onSignOff = show("a");
    fireEvent.click(await drawn("[data-cell='AUD-16:L4']"));
    expect(onSignOff).toHaveBeenCalledWith("workpaper", expect.any(String), 4);
    fireEvent.click(await drawn("[data-cell='EBP-03:L1']"));
    expect(onSignOff).toHaveBeenCalledTimes(2);
  });

  it("d: a stale cell's popover offers a re-review", async () => {
    show("d");
    fireEvent.click(await drawn("[data-cell='EBP-04:L2']"));
    expect((await drawn("[data-aud17='stale-popover']")).textContent).toContain(
      "Request re-review",
    );
  });

  it("f: no review notes", async () => {
    show("f");
    await waitFor(() => {
      expect(document.body.textContent).toContain("No review notes.");
    });
  });
});
