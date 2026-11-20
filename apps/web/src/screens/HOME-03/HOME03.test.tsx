// T-08-T16 (TASK-8842; docs/screens/HOME-03.md): "HOME-03 a-f render from data, Sep 15 lists 12
// items, and every chip states its risk in words as well as tint."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HOME03_OPENS, scenarios } from "../../fixtures/scenarios/HOME-03";
import { calendar, ridgelineDetail } from "../../fixtures/seed/home03";
import { COPY } from "./copy";
import { HOME03 } from ".";

afterEach(cleanup);

describe("HOME-03 Deadlines calendar", () => {
  it("covers a–f and three composed states", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "b", "c", "d", "e", "f", "x1", "x2", "x3"]);
    expect(Object.keys(HOME03_OPENS)).toEqual(["b", "c", "d", "e", "f"]);
  });

  it("a: Sep 15 shows three chips and +9 more; every chip says its risk in words", () => {
    render(<HOME03 calendar={calendar()} view="month" />);
    const sep15 = document.querySelector('[data-day="2026-09-15"]');
    expect(sep15?.querySelectorAll("[data-chip]")).toHaveLength(3);
    expect(screen.getByText(COPY.more(9))).toBeTruthy();
    for (const chip of document.querySelectorAll("[data-chip]")) {
      expect(chip.getAttribute("aria-label")).toMatch(/ · (\d+ days?( past due)?|Done)$/u);
    }
    expect(screen.getByText(COPY.footer)).toBeTruthy();
  });

  it("b: the list view rows", () => {
    render(<HOME03 calendar={calendar("e0", "list")} view="list" />);
    expect(document.querySelectorAll("[data-list-row]")).toHaveLength(11);
  });

  it("c: the week of Sep 13–19", () => {
    render(<HOME03 calendar={calendar()} view="week" />);
    expect(document.querySelectorAll("[data-day]")).toHaveLength(7);
  });

  it("d: Daniel Reyes's filter keeps five", () => {
    render(<HOME03 calendar={calendar("daniel")} view="month" person="Daniel Reyes" />);
    expect(document.querySelectorAll("[data-chip]")).toHaveLength(5);
  });

  it("e: the rule popover on Ridgeline", () => {
    render(<HOME03 calendar={calendar()} view="month" detail={ridgelineDetail()} />);
    expect(screen.getByText("15th day, 3rd month + 6 months (Form 7004)")).toBeTruthy();
    expect(screen.getByText("Mar 16, 2026")).toBeTruthy();
  });

  it("f: +9 more lists the 12 items of Sep 15", () => {
    render(<HOME03 calendar={calendar()} view="month" moreOpen="2026-09-15" />);
    expect(document.querySelectorAll("[data-day-popover] li")).toHaveLength(12);
  });

  it("chips route by source kind", () => {
    const onOpen = vi.fn();
    render(<HOME03 calendar={calendar()} view="month" onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button", { name: /Granite Peak · engagement letter/u }));
    expect(onOpen.mock.calls[0]?.[1]).toBe("SIG-01");
  });

  it("x1 empty filter and x2 postponed", () => {
    render(<HOME03 calendar={calendar("emptyFilter")} view="month" />);
    expect(screen.getByText(COPY.emptyFilter)).toBeTruthy();
    cleanup();
    render(<HOME03 calendar={calendar("postponed")} view="month" />);
    expect(screen.getByText(COPY.postponedFrom("Sep 21"))).toBeTruthy();
  });
});
