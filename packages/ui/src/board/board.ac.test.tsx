// ac-test-author: notanaskhan
// F-08-T26 (TASK-8939; F-08 §3 B1, B2; ADR-078): the Board kit's promises, black-box over its public
// props: a move only ever emits `onMoveIntent` (never a sign-off, approve, release, send or post
// intent; INV-1, R2); a guarded result offers "Open sign-off…", which routes to `onOpenSignOff`;
// with the run-on-move toggle disabled (or off) no intent carries `runAgent: true`, and the
// disabled toggle cannot be switched on. The keyboard "Move to…" path is the drop's twin (B1), so
// it stands in for a pointer drag in jsdom.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import { ToastHost } from "../components/toast";
import { BoardCanvas, type BoardCanvasProps } from "./index";
import type { MoveIntent, MoveResult } from "./types";

beforeAll(() => {
  installDomShims();
});

afterEach(cleanup);

const COLUMNS = [
  { key: "todo", label: "To do", count: 1 },
  { key: "review", label: "In review", count: 0 },
  { key: "complete", label: "Complete", count: 0 },
] as const;
const CARDS = [
  { id: "SURL-12", column: "todo", title: "Search for unrecorded liabilities", version: 3 },
];

function canvas(over: Partial<BoardCanvasProps> & Pick<BoardCanvasProps, "onMoveIntent">): void {
  // The app's toast host draws the board's result toasts (B1: the dark 36 px toast and its action).
  render(
    <>
      <BoardCanvas label="Board" columns={COLUMNS} cards={CARDS} {...over} />
      <ToastHost />
    </>,
  );
}

async function moveTo(column: string): Promise<void> {
  // The per-card "Move to… <title>" menu (B1's keyboard alternative), opened as a keyboard user does.
  const opener = screen.getByRole("button", { name: /^Move to…/u });
  fireEvent.keyDown(opener, { key: "ArrowDown" });
  const target = await screen.findByRole("menuitem", { name: column });
  fireEvent.click(target);
  await act(() => Promise.resolve());
}

describe("F-08 B1/B2 Board kit (independent)", () => {
  it("test_ac_b1_a_move_emits_only_a_move_intent", async () => {
    const onMoveIntent = vi.fn<(intent: MoveIntent) => Promise<MoveResult>>(() =>
      Promise.resolve({ kind: "moved" }),
    );
    const onOpenSignOff = vi.fn();
    canvas({ onMoveIntent, onOpenSignOff });
    await moveTo("In review");
    await waitFor(() => {
      expect(onMoveIntent).toHaveBeenCalledTimes(1);
    });
    expect(onMoveIntent.mock.calls[0]?.[0]).toEqual({
      cardId: "SURL-12",
      toColumn: "review",
      expectedVersion: 3,
      runAgent: false,
    });
    expect(onOpenSignOff).not.toHaveBeenCalled();
    // No control the board draws for a move is a final verb (INV-1).
    for (const b of screen.queryAllByRole("button")) {
      expect(b.textContent).not.toMatch(/^(Approve|Sign off|Release|Send|Post)(\s|$)/u);
    }
  });

  it("test_ac_b1_a_guarded_result_routes_to_open_sign_off_only", async () => {
    const onMoveIntent = vi.fn((): Promise<MoveResult> =>
      Promise.resolve({
        kind: "guarded",
        requires: "sign_off",
        text: "Moving to Complete needs a reviewer sign-off.",
      }),
    );
    const onOpenSignOff = vi.fn();
    canvas({ onMoveIntent, onOpenSignOff });
    await moveTo("Complete");
    await waitFor(() => {
      expect(onMoveIntent).toHaveBeenCalledTimes(1);
    });
    expect(onOpenSignOff).not.toHaveBeenCalled(); // the drop itself never signs off
    const open = await screen.findByRole("button", { name: /Open sign-off…/u });
    fireEvent.click(open);
    expect(onOpenSignOff).toHaveBeenCalledWith("SURL-12");
    expect(onMoveIntent).toHaveBeenCalledTimes(1);
  });

  it("test_ac_b2_a_disabled_toggle_never_dispatches_a_run", async () => {
    const onMoveIntent = vi.fn<(intent: MoveIntent) => Promise<MoveResult>>(() =>
      Promise.resolve({ kind: "moved" }),
    );
    canvas({ onMoveIntent, runOnMove: { allowed: false, on: true } });
    await moveTo("In review");
    await waitFor(() => {
      expect(onMoveIntent).toHaveBeenCalledTimes(1);
    });
    expect(onMoveIntent.mock.calls[0]?.[0].runAgent).toBe(false);
  });

  it("test_ac_b2_an_off_toggle_never_dispatches_a_run", async () => {
    const onMoveIntent = vi.fn<(intent: MoveIntent) => Promise<MoveResult>>(() =>
      Promise.resolve({ kind: "moved" }),
    );
    canvas({ onMoveIntent, runOnMove: { allowed: true, on: false } });
    await moveTo("In review");
    await waitFor(() => {
      expect(onMoveIntent).toHaveBeenCalledTimes(1);
    });
    expect(onMoveIntent.mock.calls[0]?.[0].runAgent).toBe(false);
  });

  it("test_ac_b2_an_allowed_and_on_toggle_asks_for_a_run_and_nothing_more", async () => {
    const onMoveIntent = vi.fn<(intent: MoveIntent) => Promise<MoveResult>>(() =>
      Promise.resolve({
        kind: "dispatched",
        runId: "run-1",
        text: "moved · run started · logged in Activity",
      }),
    );
    const onOpenSignOff = vi.fn();
    canvas({ onMoveIntent, onOpenSignOff, runOnMove: { allowed: true, on: true } });
    await moveTo("In review");
    await waitFor(() => {
      expect(onMoveIntent).toHaveBeenCalledTimes(1);
    });
    expect(onMoveIntent.mock.calls[0]?.[0].runAgent).toBe(true);
    expect(onOpenSignOff).not.toHaveBeenCalled();
  });
});
