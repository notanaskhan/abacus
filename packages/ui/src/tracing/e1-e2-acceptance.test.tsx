import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { type JSX, useRef } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { AgentText } from "../agent-text";
import { installDomShims } from "../test-dom";
import {
  type CitationView,
  CitationPopoverHost,
  CiteMarker,
  MATCH_LIGHT_MS,
  type MatchId,
  MatchScope,
  Matchable,
  createMatchStore,
  matchIdOf,
  useMatch,
} from "./index";

// F-05-T42: independent acceptance tests (ADR-078) for E1 MatchProvider and E2 the anchored
// popover host, written from the ACs and the plan, through the public exports only:
//   F-05-T41  "One match per scope lights every data-match element over 360 ms, and match ids come
//              only from typed citation locators, never model text (INV-2)."
//   F-05-T42  "Fake-timer intents (120, 140, 150 ms), scope anchoring, Escape refocus and
//              locator-only ids pass, and only the two affected cells re-render."
//   F-05 G1   "after 120 ms (150 ms for markers) every element with that data-match lights,
//              releases 140 ms after leave unless pinned, Escape clears and refocuses the origin,
//              and only the two affected cells re-render. The anchored popover sits 8 px beside
//              the lit cell [browser: e2e/tracing.spec.ts]."

beforeAll(installDomShims);
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const wait = (ms: number): void => {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
};

const lit = (text: string): boolean => screen.getByText(text).hasAttribute("data-lit");

const cell = (file: string, c: string): MatchId =>
  matchIdOf({ kind: "sheet_cell", file, sheet: "Sheet1", cell: c });

const A = cell("Plan.xlsx", "B2");
const B = cell("Plan.xlsx", "B3");

describe("hover intent and release (fake timers)", () => {
  it("a row lights at 120 ms, not before, with every element carrying its id", () => {
    render(
      <MatchScope>
        <Matchable id={A}>row A</Matchable>
        <Matchable id={A} kind="cell">
          cell A
        </Matchable>
        <Matchable id={B}>row B</Matchable>
      </MatchScope>,
    );
    fireEvent.pointerEnter(screen.getByText("row A"));
    wait(119);
    expect(lit("row A")).toBe(false);
    wait(1);
    expect(lit("row A")).toBe(true);
    expect(lit("cell A")).toBe(true);
    expect(lit("row B")).toBe(false);
  });

  it("releases 140 ms after the pointer leaves", () => {
    render(
      <MatchScope>
        <Matchable id={A}>row A</Matchable>
      </MatchScope>,
    );
    fireEvent.pointerEnter(screen.getByText("row A"));
    wait(120);
    fireEvent.pointerLeave(screen.getByText("row A"));
    wait(139);
    expect(lit("row A")).toBe(true);
    wait(1);
    expect(lit("row A")).toBe(false);
  });

  it("a marker lights its match at 150 ms, not at 120", () => {
    const cite: CitationView = { n: 1, title: "Plan", quote: "q", loc: "Sheet1!B2", match: A };
    render(
      <MatchScope>
        <CiteMarker cite={cite} />
        <Matchable id={A}>row A</Matchable>
      </MatchScope>,
    );
    fireEvent.pointerEnter(screen.getByRole("button", { name: "Citation 1: Plan" }));
    wait(120);
    expect(lit("row A")).toBe(false);
    wait(29);
    expect(lit("row A")).toBe(false);
    wait(1);
    expect(lit("row A")).toBe(true);
  });

  it("a pinned match does not release on leave", () => {
    function Pinnable(): JSX.Element {
      const { bind, pin } = useMatch(A);
      return (
        <button
          type="button"
          {...bind}
          onClick={(e) => {
            pin(e.currentTarget);
          }}
        >
          pin A
        </button>
      );
    }
    render(
      <MatchScope>
        <Pinnable />
      </MatchScope>,
    );
    const button = screen.getByText("pin A");
    fireEvent.click(button);
    fireEvent.pointerLeave(button);
    wait(5_000);
    expect(lit("pin A")).toBe(true);
  });
});

describe("one match per scope", () => {
  it("lighting a second id darkens the first; another scope is untouched", () => {
    render(
      <>
        <MatchScope>
          <Matchable id={A}>left A</Matchable>
          <Matchable id={B}>left B</Matchable>
        </MatchScope>
        <MatchScope>
          <Matchable id={A}>right A</Matchable>
        </MatchScope>
      </>,
    );
    fireEvent.pointerEnter(screen.getByText("left A"));
    wait(120);
    expect(lit("left A")).toBe(true);
    expect(lit("right A")).toBe(false);
    fireEvent.pointerEnter(screen.getByText("left B"));
    wait(120);
    expect(lit("left B")).toBe(true);
    expect(lit("left A")).toBe(false);
  });

  it("the light is a 360 ms transition", () => {
    expect(MATCH_LIGHT_MS).toBe(360);
    render(
      <MatchScope>
        <Matchable id={A}>row A</Matchable>
      </MatchScope>,
    );
    expect(screen.getByText("row A").className).toMatch(/duration-\[360ms\]/);
  });
});

describe("scope anchoring", () => {
  it("anchors to the element in the origin's scope before the same id elsewhere", () => {
    const store = createMatchStore();
    render(
      <>
        <MatchScope>
          <Matchable id={A}>other scope A</Matchable>
        </MatchScope>
        <MatchScope store={store as never}>
          <button type="button">origin</button>
          <Matchable id={A}>own scope A</Matchable>
        </MatchScope>
      </>,
    );
    const origin = screen.getByText("origin");
    expect(store.anchorFor(A, origin)).toBe(screen.getByText("own scope A"));
  });

  it("the popover opens anchored to the lit cell, or to the marker when nothing is lit", () => {
    const withCell: CitationView = { n: 1, title: "Plan", quote: "q", loc: "B2", match: A };
    const noCell: CitationView = { n: 2, title: "Memo", quote: "q", loc: "p. 2", match: null };
    render(
      <MatchScope>
        <CiteMarker cite={withCell} />
        <CiteMarker cite={noCell} />
        <Matchable id={A}>cell A</Matchable>
        <CitationPopoverHost />
      </MatchScope>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Citation 1: Plan" }));
    expect(screen.getByRole("dialog").getAttribute("data-anchored")).toBe("match");
    fireEvent.click(screen.getByRole("button", { name: "Citation 1: Plan" }));
    fireEvent.click(screen.getByRole("button", { name: "Citation 2: Memo" }));
    expect(screen.getByRole("dialog").getAttribute("data-anchored")).toBe("origin");
  });
});

describe("Escape", () => {
  it("clears the match and returns focus to its origin", () => {
    function Row(): JSX.Element {
      const { bind, pin } = useMatch(A);
      return (
        <button
          type="button"
          {...bind}
          onClick={(e) => {
            pin(e.currentTarget);
          }}
        >
          origin row
        </button>
      );
    }
    render(
      <MatchScope>
        <Row />
        <button type="button">elsewhere</button>
      </MatchScope>,
    );
    const origin = screen.getByText("origin row");
    fireEvent.click(origin);
    screen.getByText("elsewhere").focus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(lit("origin row")).toBe(false);
    expect(document.activeElement).toBe(origin);
  });

  it("closes the citation popover and refocuses the marker", () => {
    const cite: CitationView = { n: 1, title: "Plan", quote: "q", loc: "B2", match: A };
    render(
      <MatchScope>
        <CiteMarker cite={cite} />
        <Matchable id={A}>cell A</Matchable>
        <CitationPopoverHost />
      </MatchScope>,
    );
    const marker = screen.getByRole("button", { name: "Citation 1: Plan" });
    fireEvent.click(marker);
    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(within(dialog).getByText("B2"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(lit("cell A")).toBe(false);
    expect(document.activeElement).toBe(marker);
  });
});

describe("locator-only ids (INV-2)", () => {
  it("an id is minted from a typed locator; a bare string is a type error", () => {
    const id = matchIdOf({ kind: "workpaper_cell", sheet_id: "s", row_key: "r", column_key: "c" });
    expect(typeof id).toBe("string");
    // @ts-expect-error a string from anywhere else, model text included, is not a MatchId
    const bad: MatchId = "Plan.xlsx!B2";
    expect(bad).toBe("Plan.xlsx!B2");
    function Probe(): JSX.Element {
      // @ts-expect-error useMatch refuses a plain string
      useMatch("Plan.xlsx!B2");
      return <span />;
    }
    expect(Probe).toBeTypeOf("function");
  });

  it("model text that names a cell lights nothing; only the citation's own match does", () => {
    const uncited: CitationView = { n: 1, title: "Memo", quote: "q", loc: "p. 1", match: null };
    render(
      <MatchScope>
        <AgentText text={`The total ties to ${A} and [1].`} />
        <CiteMarker cite={uncited} />
        <Matchable id={A}>cell A</Matchable>
      </MatchScope>,
    );
    fireEvent.pointerEnter(screen.getByRole("button", { name: "Citation 1: Memo" }));
    fireEvent.pointerEnter(screen.getByText(/The total ties/));
    wait(1_000);
    expect(lit("cell A")).toBe(false);
    expect(document.querySelectorAll("[data-match][data-lit]")).toHaveLength(0);
  });
});

describe("re-renders", () => {
  it("only the two affected cells re-render when the match moves", () => {
    const renders = new Map<string, number>();
    const ids = Array.from({ length: 40 }, (_, i) => cell("Grid.xlsx", `C${String(i + 1)}`));
    function Cell({ id }: { id: MatchId }): JSX.Element {
      const { bind } = useMatch(id, "cell");
      const seen = useRef(0);
      seen.current += 1;
      renders.set(id, seen.current);
      return <span {...bind}>{id}</span>;
    }
    const store = createMatchStore();
    render(
      <MatchScope store={store as never}>
        {ids.map((id) => (
          <Cell key={id} id={id} />
        ))}
      </MatchScope>,
    );
    const first = ids[3] as MatchId;
    const second = ids[17] as MatchId;
    const before = new Map(renders);
    act(() => {
      store.light(first);
    });
    const afterFirst = ids.filter((id) => renders.get(id) !== before.get(id));
    expect(afterFirst).toEqual([first]);
    const mid = new Map(renders);
    act(() => {
      store.light(second);
    });
    const changed = ids.filter((id) => renders.get(id) !== mid.get(id));
    expect(changed.sort()).toEqual([first, second].sort());
  });
});
