// C-01-T41 (TASK-8638, DEC-5638): POR-11's transaction questions in fixture mode. Row acceptance
// (the part built here): answering a question closes the sheet and moves the row to answered with
// a receipt, and no client route returns a firm-only field.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { copperleafPortalQuestions } from "../../fixtures/seed/close-book";
import { newQueryClient } from "../../testing/support";
import { QuestionsCard } from "./index";
import { type Por11State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Por11State, props: { questionId?: string; mobile?: boolean } = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <QuestionsCard closeId="close-copperleaf-2026-08" {...props} />
    </QueryClientProvider>,
  );
}

const SOUND = copperleafPortalQuestions().items[2]?.question_id ?? "";

describe("POR-11 transaction questions", () => {
  it("a: three to answer, in the client's words only", async () => {
    show("a");
    expect(await screen.findByText("Transaction questions · 3 to answer")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Answer…" })).toHaveLength(3);
    const text = document.body.textContent;
    for (const firm of [
      "Pending incorporation",
      "Matched to uploaded document",
      "Visible to client",
    ]) {
      expect(text).not.toContain(firm);
    }
  });

  it("no client route returns a firm-only field", () => {
    const allowed = new Set([
      "question_id",
      "client_wording",
      "context_line",
      "status",
      "asked_by_name",
      "asked_at",
      "answered_at",
    ]);
    for (const q of copperleafPortalQuestions().items) {
      expect(Object.keys(q).every((k) => allowed.has(k))).toBe(true);
    }
  });

  it("b: answering closes the sheet and moves the row to answered with a receipt", async () => {
    show("b", { questionId: SOUND });
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByLabelText("Voided"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Send answer" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(screen.getByText("Transaction questions · 2 to answer")).toBeTruthy();
    expect(screen.getByText(/✓ You answered Sep 14, 1:12/)).toBeTruthy();
    const rows = [...document.querySelectorAll<HTMLElement>("[data-question]")];
    expect(rows.at(-1)?.dataset.status).toBe("answered");
  });

  it("c: the Sound Electric answer sits at the bottom, two to answer", async () => {
    show("c");
    expect(await screen.findByText("Transaction questions · 2 to answer")).toBeTruthy();
    const rows = [...document.querySelectorAll<HTMLElement>("[data-question]")];
    expect(rows.at(-1)?.dataset.question).toBe(SOUND);
  });
});
