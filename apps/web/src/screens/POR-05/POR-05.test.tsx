// POR-05 · Questions (T-02-T24). One test per artboard (a–f) on its fixture scenario, plus the
// row's acceptance: autosave shows Saved with the time, and a stale write reloads the answer
// instead of overwriting it. Axe runs on the same scenarios in e2e/screens/POR-05.spec.ts.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { STALE_FROM_ELSEWHERE } from "../../fixtures/handlers/portal-questionnaires";
import {
  CRYPTO,
  GRANITE_PEAK_QUESTIONS,
  NORTHWIND_QUESTIONS,
  RETIREMENT,
  SECTIONS,
} from "../../fixtures/seed/portal-questionnaires";
import { newQueryClient } from "../../testing/support";
import { POR05 } from ".";
import { COPY } from "./copy";
import { type Por05State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
  STALE_FROM_ELSEWHERE.clear();
});

function show(state: Por05State, mobile = false): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <POR05 mobile={mobile} />
    </QueryClientProvider>,
  );
}

describe("POR-05 questions", () => {
  it("a · default: 22 of 24 answered, three open, the sections foot to 24", async () => {
    show("a");
    expect(await screen.findAllByText(COPY.answered(22, 24))).toBeTruthy();
    expect(SECTIONS.reduce((n, [, total]) => n + total, 0)).toBe(24);
    expect(screen.getByRole("article", { name: CRYPTO.client_wording })).toBeTruthy();
    expect(screen.getByRole("article", { name: RETIREMENT.client_wording })).toBeTruthy();
    expect(screen.getByText(COPY.from("Kevin Osei", "Sep 11"))).toBeTruthy();
    expect(screen.getByText(COPY.answeredBand(22))).toBeTruthy();
    expect(screen.getByText("Did your filing status change in 2025?")).toBeTruthy();
    expect(screen.queryByText(/Accrued/)).toBeNull();
  });

  it("b · Yes on the team's question reveals the upload slot", async () => {
    show("b");
    const card = within(await screen.findByRole("article", { name: CRYPTO.client_wording }));
    expect(card.getByRole("radio", { name: COPY.yes }).getAttribute("aria-checked")).toBe("true");
    expect(card.getByText(COPY.upload1099)).toBeTruthy();
  });

  it("c · complete: 24 of 24, Mark as Done, the thanks banner", async () => {
    show("c");
    expect(await screen.findAllByText(COPY.answered(24, 24))).toBeTruthy();
    expect(screen.getByText(COPY.complete)).toBeTruthy();
    const sections = within(screen.getByRole("list", { name: COPY.sections }));
    expect(sections.getByLabelText("Retirement complete")).toBeTruthy();
  });

  it("d · fraud inquiries addressed to Dana with long answers and Submit", async () => {
    show("d");
    for (const wording of NORTHWIND_QUESTIONS) {
      expect(await screen.findByRole("article", { name: wording })).toBeTruthy();
    }
    expect(screen.getByText(COPY.onlyTeam)).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.submit })).toBeTruthy();
    expect(screen.getByText(/Addressed to you/)).toBeTruthy();
  });

  it("e · analytics questions from Hannah Leclerc", async () => {
    show("e");
    for (const wording of GRANITE_PEAK_QUESTIONS) {
      expect(await screen.findByRole("article", { name: wording })).toBeTruthy();
    }
    expect(screen.getAllByText(COPY.analyticsFrom).length).toBe(2);
  });

  it("f · empty", async () => {
    show("f");
    expect(await screen.findByText(COPY.empty)).toBeTruthy();
    expect(screen.getByText(COPY.emptyBody)).toBeTruthy();
  });

  it("autosave shows Saved with the time", async () => {
    show("a");
    const card = within(await screen.findByRole("article", { name: RETIREMENT.client_wording }));
    fireEvent.click(card.getByRole("radio", { name: COPY.no }));
    expect(await screen.findByText(COPY.saved("9:24 AM"))).toBeTruthy();
  });

  it("a stale write reloads the answer instead of overwriting it", async () => {
    show("a");
    const card = within(await screen.findByRole("article", { name: CRYPTO.client_wording }));
    STALE_FROM_ELSEWHERE.set(CRYPTO.id, "yes"); // Jonah answered on his phone
    fireEvent.click(card.getByRole("radio", { name: COPY.no }));
    await waitFor(() => {
      const fresh = within(screen.getByRole("article", { name: CRYPTO.client_wording }));
      expect(fresh.getByRole("radio", { name: COPY.yes }).getAttribute("aria-checked")).toBe(
        "true",
      );
    });
  });

  it("M · one card at a time with Next question", async () => {
    show("a", true);
    expect(await screen.findByRole("button", { name: COPY.next })).toBeTruthy();
    expect(screen.getAllByRole("article").length).toBe(1);
  });
});
