// I-01-T24: HOME-01 R2's To-dos and Mentions bands render frames h and i and a2's empty bands
// from data, outside HOME-01's live composition.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BAND_COPY } from "./copy";
import { HomeBands } from "./HomeBands";
import { BAND_SCENARIOS } from "../../../fixtures/scenarios/HOME-01";

const due = (iso: string): string => (iso === "2026-09-16" ? "Sep 16" : iso);
const time = (iso: string): string => (iso.includes("12:35") ? "12:35 PM" : "8:31 AM");

function draw(
  frame: keyof typeof BAND_SCENARIOS,
  handlers: Partial<Parameters<typeof HomeBands>[0]> = {},
) {
  const s = BAND_SCENARIOS[frame];
  return render(
    <HomeBands
      todos={s.todos}
      mentions={s.mentions}
      dueLabel={due}
      timeLabel={time}
      {...handlers}
    />,
  );
}

afterEach(cleanup);

describe("HOME-01 R2 bands", () => {
  it("a2: Daniel reads both bands empty and the header count stays 11", () => {
    draw("a2");
    expect(screen.getByText(BAND_COPY.todos.empty)).toBeTruthy();
    expect(screen.getByText(BAND_COPY.mentions.empty)).toBeTruthy();
    expect(BAND_SCENARIOS.a2.headerCount).toBe(11);
  });

  it("h: Hannah has no to-dos and two mentions, the 12:35 PM one unread", () => {
    const onOpenMention = vi.fn();
    draw("h", { onOpenMention });
    const band = screen.getByRole("region", { name: BAND_COPY.mentions.title });
    const rows = within(band).getAllByRole("button");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Margaret Okonkwo mentioned you");
    expect(rows[0]?.textContent).toContain(
      "'this cutoff item drives AJE-1 — show it as factual on the SUM.' · Northwind · Exceptions row 3",
    );
    expect(within(rows[0] as HTMLElement).getByLabelText(BAND_COPY.mentions.unread)).toBeTruthy();
    expect(rows[1]?.textContent).toContain("AUD-03 Source Documents");
    expect(rows[1]?.getAttribute("data-read")).toBe("true");
    rows[0]?.click();
    expect(onOpenMention).toHaveBeenCalledOnce();
    expect(screen.getByText(BAND_COPY.todos.empty)).toBeTruthy();
  });

  it("i: Marcus has one to-do from Margaret on Exceptions row 6, due Sep 16, and no mentions", () => {
    const onOpenTodo = vi.fn();
    draw("i", { onOpenTodo });
    const band = screen.getByRole("region", { name: BAND_COPY.todos.title });
    const row = within(band).getByRole("button");
    expect(row.textContent).toContain(
      "Request opt-out elections for the 4 auto-enrolled participants",
    );
    expect(row.textContent).toContain("from Margaret Okonkwo");
    expect(row.textContent).toContain("Northwind · Exceptions row 6");
    expect(row.textContent).toContain("Sep 16");
    row.click();
    expect(onOpenTodo).toHaveBeenCalledOnce();
    expect(screen.getByText(BAND_COPY.mentions.empty)).toBeTruthy();
  });
});
