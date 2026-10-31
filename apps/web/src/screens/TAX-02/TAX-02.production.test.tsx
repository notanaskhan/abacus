// TAX-02 in a production build (T-02-T14): "no Run draft, Re-run draft or Assistant control
// exists in a production build". PLANNED_VISIBLE folds to false, so those, the Checkpoints chip
// and the planned tabs are not drawn at all.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ReturnOverviewPage } from ".";
import { COPY } from "./copy";
import { OPENS, scenarios } from "./scenarios";

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

function show(state: "a" | "b"): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ReturnOverviewPage returnId={OPENS[state]} />
    </QueryClientProvider>,
  );
}

describe("TAX-02 production build", () => {
  it("a: no Re-run draft, Assistant or Checkpoints; Assign… and the engine link stay", async () => {
    show("a");
    await screen.findByText("Blocked by Draft K-1 · pre-release");
    expect(screen.queryByText(COPY.actions.rerun)).toBeNull();
    expect(screen.queryByText("Assistant")).toBeNull();
    expect(screen.queryByText("Checkpoints")).toBeNull();
    expect(screen.getByRole("button", { name: COPY.actions.assign })).toBeTruthy();
    expect(screen.getByText(COPY.actions.openEngine)).toBeTruthy();
    expect(screen.queryByRole("tab", { name: /Review|Issues|Activity/ })).toBeNull();
    // TAX-03 is built (T-02-T19): the Intake tab is live in production.
    expect(screen.getByRole("tab", { name: /Intake/ })).toBeTruthy();
  });

  it("b: the agents-off empty state has no Run draft", async () => {
    show("b");
    await screen.findByText(COPY.noDraftTitle);
    expect(screen.queryByRole("button", { name: COPY.runDraft })).toBeNull();
  });
});
