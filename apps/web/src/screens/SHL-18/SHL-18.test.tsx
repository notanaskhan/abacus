// P-05-T10 (SHL-18 a, b, b2, c, d, e, f): C-29 CommentThread v2 from the generated client in
// fixture mode. The menus offer Correct… and Redact…, never Edit or Delete; Convert to review
// note… is hidden on a shared thread; a person not on the engagement is greyed and not selectable.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { COMMENT_COPY as COPY, segments } from "../../domain/collaboration";
import { newQueryClient } from "../../testing/support";
import { CommentsAndMentions } from ".";
import { FRAMES, STATES, type State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CommentsAndMentions
        state={state}
        onConvertToTodo={() => undefined}
        onClose={() => undefined}
      />
    </QueryClientProvider>,
  );
}

const thread = (): HTMLElement | null => document.querySelector("[data-c29='thread']");

describe("SHL-18 comments and mentions", () => {
  it.each(STATES)("%s renders its variant at the handoff width", async (state) => {
    show(state);
    await waitFor(() => {
      expect(thread()).not.toBeNull();
    });
    const width = { popover: "420px", dock: "360px", drawer: "480px" }[FRAMES[state].variant];
    expect(thread()?.getAttribute("data-variant")).toBe(FRAMES[state].variant);
    expect(thread()?.style.width).toBe(width);
    expect(screen.getByText(COPY.legend)).toBeTruthy();
  });

  it("a: Margaret's comment on Exceptions!A3, Hannah notified", async () => {
    show("a");
    await screen.findByText(/this cutoff item drives AJE-1/);
    expect(screen.getByText("Exceptions!A3 · Northwind PY2025")).toBeTruthy();
    expect(document.querySelector("[data-c29='mention']")?.textContent).toBe("@Hannah Leclerc");
    expect(document.querySelector("[data-c29='delivery']")?.textContent).toContain(
      "Hannah Leclerc notified in Accrued and by email",
    );
    expect(screen.getByText(COPY.hint)).toBeTruthy();
    expect(screen.getByPlaceholderText(COPY.placeholder)).toBeTruthy();
  });

  it("a: the thread menu converts and mutes, and never edits or deletes", async () => {
    show("a");
    await screen.findByText(/this cutoff item drives AJE-1/);
    // Enter opens the menu (a pointer-down as well would toggle it shut again in jsdom).
    fireEvent.keyDown(screen.getByRole("button", { name: COPY.more }), { key: "Enter" });
    const items = await screen.findAllByRole("menuitem");
    const labels = items.map((i) => i.textContent);
    expect(labels).toEqual(
      expect.arrayContaining([COPY.copyLink, COPY.toTodo, COPY.toReviewNote, COPY.mute]),
    );
    expect(labels.some((l) => /^Edit|^Delete/.test(l))).toBe(false);
  });

  it("b: '@Ha' lists Hannah Leclerc with Ha in 500", async () => {
    show("b");
    const listbox = await screen.findByRole("listbox", { name: "Mention someone" });
    expect(listbox.textContent).toContain("Hannah Leclerc");
    expect(screen.getByRole("combobox", { name: "Comment" }).getAttribute("aria-expanded")).toBe(
      "true",
    );
    expect(screen.getByText(COPY.pickerKeys)).toBeTruthy();
  });

  it("b2: a bare '@' offers the team entry and the five members", async () => {
    show("b2");
    const listbox = await screen.findByRole("listbox", { name: "Mention someone" });
    expect(listbox.textContent).toContain("Northwind PY2025 team · 5 people");
    expect(listbox.querySelectorAll("[role='option']").length).toBe(6);
  });

  it("c: Simone Baptiste is greyed, not selectable, with the restricted footer", async () => {
    show("c");
    const greyed = await screen.findByLabelText(`Simone Baptiste, ${COPY.notOnEngagement}`);
    expect(greyed.getAttribute("aria-disabled")).toBe("true");
    expect(greyed.getAttribute("role")).toBeNull();
    expect(screen.getByText(COPY.restricted)).toBeTruthy();
  });

  it("d: the resolved dividends thread in the dock with Reopen", async () => {
    show("d");
    await screen.findByText(/Resolved by Hannah Leclerc/);
    expect(screen.getByRole("button", { name: COPY.reopen })).toBeTruthy();
    expect(screen.getByText(/dividends paid now shows 1,100,000/)).toBeTruthy();
    expect(screen.queryByPlaceholderText(COPY.placeholder)).toBeNull();
  });

  it("e: the row drawer's empty state", async () => {
    show("e");
    await screen.findByText(COPY.emptyTitle);
    expect(screen.getByText(COPY.emptyBody)).toBeTruthy();
  });

  it("f: a shared thread names who sees it and hides Convert to review note…", async () => {
    show("f");
    await screen.findByText(/Allocated from group PM 180,000/);
    expect(screen.getByText(COPY.visibleTo("Pruett & Lang LLP"))).toBeTruthy();
    expect(screen.getByText(COPY.sharedHint("Pruett & Lang LLP"))).toBeTruthy();
    expect(screen.queryByRole("menuitem", { name: COPY.toReviewNote })).toBeNull();
  });
});

describe("mention tokens", () => {
  it("split a body into text and the mentioned people's tokens", () => {
    expect(segments("@Hannah Leclerc this cutoff", ["Hannah Leclerc"])).toEqual([
      { text: "@Hannah Leclerc", mention: true },
      { text: " this cutoff", mention: false },
    ]);
    expect(segments("no one", [])).toEqual([{ text: "no one", mention: false }]);
  });
});
