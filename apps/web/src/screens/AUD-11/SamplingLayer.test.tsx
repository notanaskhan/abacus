// AUD-11 over a host that is not its cockpit (S47, TASK-8338): `?ov=sampling:<workItemId>` draws
// the same live canvas AUD-02 draws, in a full sheet, on AUD-11 a's fixtures.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_PARTICIPANTS, northwindParticipants } from "../../fixtures/seed/sampling";
import { ov } from "../../routes/to";
import { newQueryClient } from "../../testing/support";
import { SamplingLayer } from "./SamplingLayer";
import { scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

describe("AUD-11 sampling layer", () => {
  it("draws the work item's sample set in a full sheet", async () => {
    restore = installFixtureMode(scenarios.a);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <SamplingLayer
          ref={ov.AUD11(northwindParticipants().work_item_id)}
          index={0}
          close={() => undefined}
        />
      </QueryClientProvider>,
    );
    const sheet = await screen.findByRole("dialog", { name: "Sample Selection" });
    await waitFor(
      () => {
        expect(sheet.querySelectorAll("[data-aud11='items'] [data-item]")).toHaveLength(
          NORTHWIND_PARTICIPANTS.length,
        );
      },
      { timeout: 6000 },
    );
    expect(
      within(sheet).getAllByText(NORTHWIND_PARTICIPANTS[0]?.[0] ?? "").length,
    ).toBeGreaterThan(0);
  });
});
