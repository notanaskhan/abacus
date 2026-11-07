// A-06-T31 (ADR-078): independent tests of the AUD-17 UI, from the row and the contract: chips never
// sign, comments are never counted, the legend isn't a filter, and the totals are the server's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type Scenario, installFixtureMode, json } from "../../app-core/fixture-mode";
import { AUD17_ENGAGEMENT, AUD17_WORK_ITEM, aud17Matrix } from "../../fixtures/seed/aud17";
import { newQueryClient } from "../../testing/support";
import { ReviewNotesPane } from "./Notes";
import { scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  vi.restoreAllMocks();
});

function show(scenario: Scenario): ReturnType<typeof vi.fn> {
  const onSignOff = vi.fn();
  restore = installFixtureMode(scenario);
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

function writes(calls: readonly (readonly unknown[])[]): string[] {
  return calls
    .map(([input, init]) => {
      const fromInit = (init as RequestInit | undefined)?.method;
      return fromInit ?? (input instanceof Request ? input.method : "GET");
    })
    .filter((method) => method !== "GET");
}

describe("A-06-T31: AUD-17's UI", () => {
  it("a chip can't create a sign-off: clicking every cell writes nothing", async () => {
    const onSignOff = show(scenarios.a);
    await drawn("[data-cell]");
    const spy = vi.spyOn(globalThis, "fetch");
    const cells = [...document.querySelectorAll<HTMLElement>("[data-cell]")];
    for (const cell of cells) fireEvent.click(cell);
    expect(writes(spy.mock.calls)).toEqual([]);
    expect(onSignOff.mock.calls.length).toBeGreaterThan(0);
  });

  it("the footer shows the server's totals, whatever the rows would add up to", async () => {
    const matrix = aud17Matrix();
    const scenario: Scenario = {
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        "GET /v1/work-items/{work_item_id}/sign-off-matrix": () =>
          json({
            ...matrix,
            footer: {
              ...matrix.footer,
              partner_signed: 97,
              partner_required: 99,
              changed_after_sign_off: 41,
            },
          }),
      },
    };
    show(scenario);
    const footer = await drawn("[data-aud17='footer']");
    await waitFor(() => {
      expect(footer.textContent).toContain("Partner 97 of 99");
    });
    expect(footer.textContent).toContain("Changed after sign-off 41");
  });

  it("comments never count: the legend says so and the footer has no comment figure", async () => {
    show(scenarios.a);
    expect((await drawn("[data-aud17='legend']")).textContent).toContain("a comment never does");
    expect((await drawn("[data-aud17='footer']")).textContent.toLowerCase()).not.toContain(
      "comment",
    );
  });

  it("the legend isn't a filter: it holds no control, and a click changes no row", async () => {
    show(scenarios.a);
    const legend = await drawn("[data-aud17='legend']");
    expect(legend.querySelectorAll("button, a, input, [role='button']")).toHaveLength(0);
    await drawn("[data-cell]");
    const before = document.querySelectorAll("[data-row]").length;
    fireEvent.click(legend);
    expect(document.querySelectorAll("[data-row]")).toHaveLength(before);
  });
});
