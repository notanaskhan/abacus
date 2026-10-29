// TAX-01 in a production build (T-02-T12): "production builds show no Board toggle, Extend or Run
// firm standards item". PLANNED_VISIBLE folds to false, so the planned items are not drawn at all.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { TaxReturnsPage } from ".";
import { COPY } from "./copy";
import { SELECTED_IDS, scenarios } from "./scenarios";

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

describe("TAX-01 production build", () => {
  it("draws no Board toggle, Extend… or Run firm standards…", async () => {
    restore = installFixtureMode(scenarios.d);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <TaxReturnsPage initialSelection={SELECTED_IDS} />
      </QueryClientProvider>,
    );
    await waitFor(() => {
      expect(document.querySelectorAll("tr[data-row]").length).toBeGreaterThan(0);
    });
    const bar = screen.getByRole("region", { name: "3 selected" });
    expect(within(bar).getByRole("button", { name: COPY.bulk.assign })).toBeTruthy();
    expect(screen.queryByText(COPY.bulk.extend)).toBeNull();
    expect(screen.queryByText(COPY.bulk.standards)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: COPY.bulkActions }));
    expect(screen.queryByRole("menuitem", { name: COPY.bulk.extend })).toBeNull();
    expect(screen.queryByRole("menuitem", { name: COPY.bulk.standards })).toBeNull();
    expect(screen.queryByRole("button", { name: /Board/ })).toBeNull();
  });
});
