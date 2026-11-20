// F-08-T18 (TASK-8844; F-08 §B1; T19b–d): "A guarded result springs back in 240 ms with 'Moving to
// Complete needs a reviewer sign-off. Open sign-off...', and every drag has a keyboard and menu
// equivalent."
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { toastStore } from "../components/toast";
import { installDomShims } from "../test-dom";
import { BoardCanvas } from "./BoardCanvas";
import {
  type BoardCardVM,
  type BoardColumn,
  type MoveIntent,
  type MoveResult,
  SPRING_BACK_MS,
} from "./types";

installDomShims();
afterEach(() => {
  cleanup();
  toastStore.clear();
});

const COLUMNS: BoardColumn[] = [
  { key: "not_started", label: "Not started", count: 1 },
  { key: "in_progress", label: "In progress", count: 0 },
  { key: "complete", label: "Complete", count: 0 },
  { key: "archived", label: "Archived", count: 0, accepts: false },
];
const CARDS: BoardCardVM[] = [{ id: "p1", column: "not_started", title: "Cash", version: 3 }];
const GUARD = "Moving to Complete needs a reviewer sign-off.";

async function moveVia(
  menu: string,
  result: MoveResult,
  extra: Partial<Parameters<typeof BoardCanvas>[0]> = {},
) {
  const onMoveIntent = vi.fn<(intent: MoveIntent) => Promise<MoveResult>>(() =>
    Promise.resolve(result),
  );
  const onOpenSignOff = vi.fn();
  render(
    <BoardCanvas
      label="Board"
      columns={COLUMNS}
      cards={CARDS}
      onMoveIntent={onMoveIntent}
      onOpenSignOff={onOpenSignOff}
      {...extra}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Move to… Cash" }));
  await act(() => {
    fireEvent.click(screen.getByRole("menuitem", { name: menu }));
    return Promise.resolve();
  });
  return { onMoveIntent, onOpenSignOff };
}

describe("BoardCanvas (F-08-T18)", () => {
  it("the Move to menu sends the same intent a drag would, runAgent false by default", async () => {
    const { onMoveIntent } = await moveVia("In progress", { kind: "moved" });
    expect(onMoveIntent).toHaveBeenCalledWith({
      cardId: "p1",
      toColumn: "in_progress",
      expectedVersion: 3,
      runAgent: false,
    });
    expect(
      document.querySelector('[data-board-column="in_progress"] [data-board-card="p1"]'),
    ).not.toBeNull();
    expect(document.querySelector("[data-board-announce]")?.textContent).toBe(
      "Cash moved from Not started to In progress.",
    );
  });

  it("a guarded result springs back and the toast's action opens the sign-off", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { onOpenSignOff } = await moveVia("Complete", {
      kind: "guarded",
      requires: "sign_off",
      text: GUARD,
    });
    act(() => {
      vi.advanceTimersByTime(SPRING_BACK_MS);
    });
    expect(
      document.querySelector('[data-board-column="not_started"] [data-board-card="p1"]'),
    ).not.toBeNull();
    expect(SPRING_BACK_MS).toBe(240);
    const t = toastStore.list().at(-1);
    expect(t?.text).toBe(GUARD);
    expect(t?.action).toBe("Open sign-off…");
    act(() => {
      toastStore.act(t?.id ?? "");
    });
    expect(onOpenSignOff).toHaveBeenCalledWith("p1");
    vi.useRealTimers();
  });

  it("a non-accepting column is disabled in the menu", () => {
    render(<BoardCanvas label="Board" columns={COLUMNS} cards={CARDS} onMoveIntent={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Move to… Cash" }));
    expect(screen.getByRole("menuitem", { name: "Archived" }).getAttribute("aria-disabled")).toBe(
      "true",
    );
  });

  it("runAgent rides only when the policy allows it and the toggle is on", async () => {
    const { onMoveIntent } = await moveVia(
      "In progress",
      { kind: "dispatched", runId: "r1", text: "moved · run started · logged in Activity" },
      { runOnMove: { allowed: true, on: true } },
    );
    expect(onMoveIntent.mock.calls[0]?.[0]).toMatchObject({ runAgent: true });
    cleanup();
    const second = await moveVia(
      "In progress",
      { kind: "moved" },
      { runOnMove: { allowed: false, on: true } },
    );
    expect(second.onMoveIntent.mock.calls[0]?.[0]).toMatchObject({ runAgent: false });
  });

  it("the intent carries no sign-off, approve, release, send or post (INV-1)", async () => {
    const { onMoveIntent } = await moveVia("Complete", { kind: "moved" });
    expect(Object.keys(onMoveIntent.mock.calls[0]?.[0] as object).sort()).toEqual([
      "cardId",
      "expectedVersion",
      "runAgent",
      "toColumn",
    ]);
  });

  it("a keyboard sensor is registered (the drag has a keyboard path)", () => {
    render(<BoardCanvas label="Board" columns={COLUMNS} cards={CARDS} onMoveIntent={vi.fn()} />);
    const card = document.querySelector('[data-board-card="p1"]');
    expect(card?.getAttribute("role")).toBe("button");
    expect(card?.getAttribute("aria-roledescription")).toBe("sortable");
  });
});
