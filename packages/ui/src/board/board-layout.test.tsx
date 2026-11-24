// F-08-T22 (TASK-8928; F-08 §B2, §B3; DEC-5930): "T19a to T19l render, the toggle is disabled with
// 'Not allowed for this engagement type by AI policy' when policy forbids it, and column counts
// sum to the tiles." Plus: no intent carries runAgent unless allowed and on (B2), filters hide
// empty lanes with Clear, the Binder tree table, the guarded drop never signs (INV-1).
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { T19_STATES, T19Board, t19Props } from "../specimens/t19-board";
import { BoardLayout, RUN_ON_MOVE_DENIED } from ".";

afterEach(cleanup);

describe("BoardLayout T19", () => {
  it.each(T19_STATES)("T19%s renders", (st) => {
    render(<T19Board state={st} />);
    expect(document.querySelector(`[data-t19="${st}"] [data-board-layout]`)).not.toBeNull();
  });

  it("a: four 262 columns, two lanes, three C-24 cards; the counts sum to the tiles", () => {
    render(<T19Board state="a" />);
    const headers = [...document.querySelectorAll("[data-column-header]")];
    expect(headers.map((h) => h.getAttribute("data-column-header"))).toEqual([
      "Not started",
      "In progress",
      "In review",
      "Complete",
    ]);
    const counts = headers.map((h) => Number(h.querySelector("[data-count]")?.textContent));
    const tiles = t19Props("a").cards.length;
    expect(counts.reduce((a, b) => a + b, 0)).toBe(tiles);
    expect(document.querySelectorAll("[data-lane]")).toHaveLength(2);
    expect(document.querySelectorAll("[data-card]")).toHaveLength(3);
  });

  it("h: the control set has six columns, the navigator rail, and the toggle disabled by policy", () => {
    render(<T19Board state="h" />);
    expect(document.querySelectorAll("[data-column-header]")).toHaveLength(6);
    expect(document.querySelector('[data-navigator="rail"]')).not.toBeNull();
    const toggle = screen.getByRole("switch", { name: "Run agent on move" });
    expect(
      toggle.hasAttribute("disabled") || toggle.getAttribute("aria-disabled") === "true",
    ).toBe(true);
    expect(document.querySelector('[data-run-on-move="denied"]')).not.toBeNull();
    expect(RUN_ON_MOVE_DENIED).toBe("Not allowed for this engagement type by AI policy");
  });

  it("a denied policy never sends runAgent, even if the host says on", () => {
    const intents: boolean[] = [];
    const props = t19Props("a");
    render(
      <BoardLayout
        {...props}
        runOnMove={{ allowed: false, on: true }}
        onMoveIntent={(i) => {
          intents.push(i.runAgent);
          return Promise.resolve({ kind: "moved" });
        }}
      />,
    );
    const toggle = screen.getByRole("switch", { name: "Run agent on move" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    const move = screen.getAllByRole("button", { name: /^Move to… Program one/ })[0];
    expect(move).toBeTruthy();
    expect(intents.every((r) => !r)).toBe(true);
  });

  it("e: the filter hides the empty lane and offers Clear", () => {
    render(<T19Board state="e" />);
    expect(document.querySelectorAll("[data-lane]")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
  });

  it("f empty and g loading: the designed EmptyState, then real headers with six skeleton cards", () => {
    render(<T19Board state="f" />);
    expect(screen.getByText("No programs yet.")).toBeTruthy();
    expect(
      screen.getByText("Programs appear when the engagement template is applied."),
    ).toBeTruthy();
    cleanup();
    render(<T19Board state="g" />);
    expect(document.querySelectorAll("[data-column-header]")).toHaveLength(4);
    expect(document.querySelector("[data-board-loading]")?.children).toHaveLength(6);
  });

  it("i: Binder is a tree table with a folder row per area", () => {
    render(<T19Board state="i" />);
    expect(document.querySelectorAll("[data-binder-folder]")).toHaveLength(2);
    expect(document.querySelectorAll("[data-binder-row]")).toHaveLength(3);
    expect(screen.getByRole("columnheader", { name: "Preparer sign-offs" })).toBeTruthy();
  });

  it("l: Group B is collapsed and shows 1 of 1", () => {
    render(<T19Board state="l" />);
    expect(document.querySelector('[data-lane="Group B"] [data-lane-done]')?.textContent).toBe(
      "1 of 1",
    );
  });

  it("a guarded drop opens sign-off and never signs (INV-1)", async () => {
    const opened = vi.fn();
    const props = t19Props("a");
    render(
      <BoardLayout
        {...props}
        onOpenSignOff={opened}
        onMoveIntent={() =>
          Promise.resolve({
            kind: "guarded",
            requires: "sign_off",
            text: "Moving to Complete needs a reviewer sign-off.",
          })
        }
      />,
    );
    await act(async () => {
      await Promise.resolve();
    });
    for (const word of ["Sign off", "Approve", "Release", "Send", "Post"]) {
      expect(screen.queryByRole("button", { name: new RegExp(`^${word}`) })).toBeNull();
    }
    expect(opened).not.toHaveBeenCalled();
  });
});
