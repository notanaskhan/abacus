import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { vi } from "vitest";
import { installDomShims } from "../test-dom";
import {
  CitationChip,
  CitationFooter,
  CitationPopover,
  CitationPopoverHost,
  CiteMarker,
} from "./cite";
import { MatchScope, Matchable } from "./match";
import {
  INTENT_MS,
  MARKER_INTENT_MS,
  MARKER_RELEASE_MS,
  RELEASE_MS,
  contractMatchId,
  createMatchStore,
  matchIdOf,
} from "./match-store";
import type { CitationPayload, CitationView } from "./types";

// F-05-T41: the builder's tests for E1 MatchStore, E2 AnchoredPopoverHost and the C-07 visuals.
// The independent acceptance tests (ADR-078) are e1-e2-acceptance.test.tsx (F-05-T42).

beforeAll(installDomShims);
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const TB = matchIdOf({ kind: "sheet_cell", file: "TB.xlsx", sheet: "Net assets", cell: "D8" });
const PAGE = matchIdOf({ kind: "document_text", evidence_version_id: "ev1", page: 3 });

const CITES: CitationView[] = [
  {
    n: 1,
    title: "Trial balance",
    quote: "Net assets 16,812,400.00",
    loc: "Net assets!D8",
    match: TB,
  },
  { n: 2, title: "Trust report", quote: "Net trust assets", loc: "Page 3", match: PAGE },
  { n: 3, title: "Methodology", quote: "Agree the trial balance", loc: "Step 4", match: null },
];

describe("matchIdOf: the C4 derivations (§3.1)", () => {
  it("derives each kind's id as the server does", () => {
    expect(TB).toBe("TB.xlsx!D8");
    expect(
      matchIdOf({
        kind: "document_text",
        evidence_version_id: "v9",
        page: 2,
        bbox: [10, 20, 30, 40],
      }),
    ).toBe("ev:v9#p2:10,20,30,40");
    expect(
      matchIdOf({ kind: "ledger_line", ledger_snapshot_id: "s1", account_code: "1100" }),
    ).toBe("led:s1:1100");
    expect(
      matchIdOf({ kind: "workpaper_cell", sheet_id: "w", row_key: "r", column_key: "c" }),
    ).toBe("wp:w.r.c");
    expect(
      matchIdOf({ kind: "methodology_step", template_version_id: "v3", step_key: "AP-10.4" }),
    ).toBe("ms:AP-10.4@v3");
    expect(
      matchIdOf({ kind: "policy_rule", threshold_policy_id: "p", version: 2, rule_key: "r" }),
    ).toBe("pol:p@v2");
    expect(
      matchIdOf({ kind: "record_field", record_type: "client", record_id: "c1", field: "ein" }),
    ).toBe("rec:client:c1.ein");
    expect(matchIdOf({ kind: "tax_form_line", return_id: "r", form: "1040", line: "2a" })).toBe(
      "tax:r:1040:2a",
    );
    expect(matchIdOf({ kind: "artifact_cell", run_artifact_id: "a", cell: "B4" })).toBe(
      "art:a!B4",
    );
    expect(matchIdOf({ kind: "request_item", request_item_id: "q" })).toBe("req:q");
    expect(contractMatchId({ kind: "sheet_cell", match_id: "TB.xlsx!D8" })).toBe(TB);
  });
});

describe("MatchStore", () => {
  it("a row lights after 120ms, a marker after 150ms; leaving releases after 140ms", () => {
    const store = createMatchStore();
    store.intent(TB, null, "row");
    act(() => void vi.advanceTimersByTime(INTENT_MS - 1));
    expect(store.get().id).toBeNull();
    act(() => void vi.advanceTimersByTime(1));
    expect(store.get().id).toBe(TB);
    store.release("row");
    act(() => void vi.advanceTimersByTime(RELEASE_MS - 1));
    expect(store.get().id).toBe(TB);
    act(() => void vi.advanceTimersByTime(1));
    expect(store.get().id).toBeNull();
    store.intent(PAGE, null, "marker");
    act(() => void vi.advanceTimersByTime(MARKER_INTENT_MS - 1));
    expect(store.get().id).toBeNull();
    act(() => void vi.advanceTimersByTime(1));
    expect(store.get().id).toBe(PAGE);
  });

  it("a pin holds through leave and hover elsewhere; a second click unpins", () => {
    const store = createMatchStore();
    const origin = document.createElement("button");
    store.togglePin(TB, origin);
    store.release("row");
    store.intent(PAGE, null, "row");
    act(() => void vi.advanceTimersByTime(1000));
    expect(store.get()).toMatchObject({ id: TB, pinned: true });
    store.togglePin(TB, origin);
    expect(store.get().id).toBeNull();
  });

  it("moving from one row to the next never goes dark in between", () => {
    const store = createMatchStore();
    store.light(TB);
    store.release("row");
    store.intent(PAGE, null, "row");
    act(() => void vi.advanceTimersByTime(INTENT_MS));
    expect(store.get().id).toBe(PAGE);
  });

  it("anchors in the origin's scope first, falls back from a range to its cell and its sheet", () => {
    render(
      <>
        <div data-match-scope="" id="a">
          <button type="button" id="o" />
          <span id="a1" data-match="TB.xlsx!D8" />
        </div>
        <div data-match-scope="" id="b">
          <span id="b1" data-match="TB.xlsx!D8" />
          <span id="b2" data-match="TB.xlsx!D6" />
        </div>
      </>,
    );
    const store = createMatchStore();
    const origin = document.getElementById("o");
    expect(store.anchorFor(TB, origin)?.id).toBe("a1");
    const range = matchIdOf({ kind: "sheet_cell", file: "TB.xlsx", sheet: "s", cell: "D6:D7" });
    expect(store.anchorFor(range, origin)?.id).toBe("b2");
    const other = matchIdOf({ kind: "sheet_cell", file: "TB.xlsx", sheet: "s", cell: "Z9" });
    expect(store.anchorFor(other, origin)?.id).toBe("a1");
    const nowhere = matchIdOf({ kind: "request_item", request_item_id: "x" });
    expect(store.anchorFor(nowhere, origin)).toBe(origin);
  });
});

describe("Matchable and the light", () => {
  it("lights every element of the match in the scope, and only those", () => {
    render(
      <MatchScope>
        <Matchable id={TB} kind="row">
          row
        </Matchable>
        <Matchable id={TB} kind="cell">
          cell
        </Matchable>
        <Matchable id={PAGE} kind="region">
          region
        </Matchable>
      </MatchScope>,
    );
    fireEvent.pointerEnter(screen.getByText("row"));
    act(() => void vi.advanceTimersByTime(INTENT_MS));
    expect(screen.getByText("row").hasAttribute("data-lit")).toBe(true);
    expect(screen.getByText("cell").hasAttribute("data-lit")).toBe(true);
    expect(screen.getByText("region").hasAttribute("data-lit")).toBe(false);
    expect(screen.getByText("cell").className).toContain("duration-[360ms]");
  });
});

describe("C-07 visuals", () => {
  it("a marker names itself, lights after 150ms and opens the popover in the host", () => {
    render(
      <MatchScope>
        <p>
          Net assets tie
          <CiteMarker cite={CITES[0] as CitationView} list={CITES} />
        </p>
        <Matchable id={TB} kind="cell">
          16,812,400.00
        </Matchable>
        <CitationPopoverHost />
      </MatchScope>,
    );
    const marker = screen.getByRole("button", { name: "Citation 1: Trial balance" });
    expect(marker.getAttribute("aria-expanded")).toBe("false");
    fireEvent.pointerEnter(marker);
    act(() => void vi.advanceTimersByTime(MARKER_INTENT_MS));
    expect(screen.getByText("16,812,400.00").hasAttribute("data-lit")).toBe(true);
    expect(marker.getAttribute("aria-expanded")).toBe("true");
    const popover = screen.getByRole("dialog", { name: "Citation" });
    expect(popover.getAttribute("data-anchored")).toBe("match");
    expect(screen.getByText("Net assets!D8")).toBeTruthy();
    expect(screen.getByText("1 of 3")).toBeTruthy();
    // The pointer moves into the popover: it stays; it leaves: 200ms later it closes.
    fireEvent.pointerLeave(marker);
    fireEvent.pointerEnter(popover);
    act(() => void vi.advanceTimersByTime(1000));
    expect(screen.queryByRole("dialog", { name: "Citation" })).not.toBeNull();
    fireEvent.pointerLeave(popover);
    act(() => void vi.advanceTimersByTime(MARKER_RELEASE_MS));
    expect(screen.queryByRole("dialog", { name: "Citation" })).toBeNull();
  });

  it("‹ › step through the sources and re-light each; a source with nothing lit anchors to the marker", () => {
    render(
      <MatchScope>
        <CiteMarker cite={CITES[0] as CitationView} list={CITES} />
        <Matchable id={TB}>tb</Matchable>
        <Matchable id={PAGE}>page</Matchable>
        <CitationPopoverHost />
      </MatchScope>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Citation 1: Trial balance" }));
    expect(screen.getByText("tb").hasAttribute("data-lit")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Next source" }));
    expect(screen.getByText("page").hasAttribute("data-lit")).toBe(true);
    expect(screen.getByText("tb").hasAttribute("data-lit")).toBe(false);
    expect(screen.getByText("2 of 3")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next source" }));
    expect(screen.getByText("3 of 3")).toBeTruthy();
    expect(screen.getByRole("dialog", { name: "Citation" }).getAttribute("data-anchored")).toBe(
      "origin",
    );
    expect(screen.getByRole("button", { name: "Next source" })).toHaveProperty("disabled", true);
  });

  it("the popover shows the location always, the quote through AgentText, and one citation alone", () => {
    const payload: CitationPayload = { list: [CITES[1] as CitationView], index: 0 };
    const onOpenDialog = vi.fn();
    render(<CitationPopover payload={payload} onOpenDialog={onOpenDialog} />);
    expect(screen.getByText("Page 3")).toBeTruthy();
    expect(screen.getByText("1 citation")).toBeTruthy();
    expect(screen.getByText("Net trust assets").getAttribute("data-actor")).toBe("agent");
    fireEvent.click(screen.getByRole("button", { name: "Open citation…" }));
    expect(onOpenDialog).toHaveBeenCalledWith(CITES[1]);
  });

  it("the footer chips count their items and list name and location", () => {
    render(
      <CitationFooter>
        <CitationChip kind="citations" citations={CITES} forceState="open" />
        <CitationChip
          kind="procedures"
          procedures={[{ ref: "AP-10", title: "General planning" }]}
        />
      </CitationFooter>,
    );
    expect(screen.getByRole("button", { name: "Citations (3)" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Procedures (1)" })).toBeTruthy();
    const rows = screen.getAllByRole("menuitem");
    expect(rows.map((r) => r.textContent)).toEqual([
      "Trial balanceNet assets!D8",
      "Trust reportPage 3",
      "MethodologyStep 4",
    ]);
  });
});
