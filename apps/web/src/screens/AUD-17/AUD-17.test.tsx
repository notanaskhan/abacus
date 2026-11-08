// A-06-T24 (TASK-3320): AUD-17 in fixture mode. Row: "Every AUD-17 artboard renders from its scenario,
// chips open SHL-12 and never sign, and the legend states that a review note blocks sign-off and a
// comment never does."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type Scenario, installFixtureMode, json } from "../../app-core/fixture-mode";
import {
  AUD17_ENGAGEMENT,
  AUD17_WORK_ITEM,
  aud17Detail,
  aud17Notes,
} from "../../fixtures/seed/aud17";
import { newQueryClient } from "../../testing/support";
import { ReviewNotesPane } from "./Notes";
import { COPY } from "./copy";
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

function show(state: Aud17State | Scenario): ReturnType<typeof vi.fn> {
  const onSignOff = vi.fn();
  restore = installFixtureMode(typeof state === "string" ? scenarios[state] : state);
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
      "A review note blocks sign-off; a comment never does",
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

  // S28 partials (TASK-3394): the server offers Reopen on a cleared note, and the thread of a note
  // on a paper changed after a sign-off carries the amber notice.
  it("a: a note on the changed paper carries the amber notice; an open note has no Reopen", async () => {
    show("a");
    expect((await drawn("[data-aud17='stale-notice']")).textContent).toBe(COPY.staleNotice);
    const reopen = await drawn("[data-aud17='reopen']");
    expect((reopen as HTMLButtonElement).disabled).toBe(true);
  });

  it("b: a cleared note offers Reopen, and Send reopens it with why", async () => {
    const reopened = vi.fn();
    const rn13 = aud17Notes("b").items.find(
      (n) => n.status === "cleared" && n.anchor?.ref === "EBP-04!K18",
    )?.id;
    expect(rn13).toBeDefined();
    const scenario: Scenario = {
      ...scenarios.b,
      handlers: {
        ...scenarios.b.handlers,
        "POST /v1/review-notes/{note_id}/reopen": ({ params, body }) => {
          reopened(params.note_id, body);
          return json(aud17Detail(String(params.note_id), "a"));
        },
      },
    };
    show(scenario);
    const head = await drawn("[data-issue-group='cleared'] button[aria-expanded]");
    if (head.getAttribute("aria-expanded") === "false") fireEvent.click(head);
    fireEvent.click(await drawn(`[data-issue-row='${String(rn13)}']`));
    const reopen = await drawn("[data-aud17='reopen']");
    await waitFor(() => {
      expect((reopen as HTMLButtonElement).disabled).toBe(false);
    });
    expect(document.querySelector("[aria-label='Reply…']")).toBeNull();
    fireEvent.click(reopen);
    const box = await drawn("[aria-label='Reply…']");
    fireEvent.change(box, { target: { value: "The projection method is still missing" } });
    const form = box.closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form as HTMLFormElement);
    await waitFor(() => {
      expect(reopened).toHaveBeenCalledWith(String(rn13), {
        body: "The projection method is still missing",
      });
    });
  }, 20000);

  it("f: no review notes", async () => {
    show("f");
    await waitFor(() => {
      expect(document.body.textContent).toContain("No review notes.");
    });
  });
});
