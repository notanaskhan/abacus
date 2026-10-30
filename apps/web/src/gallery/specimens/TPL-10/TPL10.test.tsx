// TPL-10 · Ridgeline preparer memo specimen (F-06-T16). The row's acceptance: memo figures foot
// (1,231,600; 1,256,200; 733,500) and match TPL-06, hovering [1]–[5] lights the cited KV row, the
// letter specimen holds no agent prose, and the approved memo names Samuel Ito.
import { MatchScope } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { BRIDGE, DEPRECIATION, MEMO_SECTIONS } from "../../../fixtures/seed/tax";
import { newQueryClient } from "../../../testing/support";
import { Tpl10Board, tpl10Document } from ".";

afterEach(cleanup);

function show(state: "a" | "b" | "c" | "d"): void {
  render(
    <QueryClientProvider client={newQueryClient()}>
      <MatchScope>
        <Tpl10Board state={state} />
      </MatchScope>
    </QueryClientProvider>,
  );
}

describe("TPL-10", () => {
  it("the memo's figures foot", () => {
    const sum = (xs: readonly string[]): number => xs.reduce((a, x) => a + Number(x), 0);
    expect(sum([BRIDGE.rents, BRIDGE.parking, BRIDGE.rentalExpenses])).toBe(
      Number(BRIDGE.netRental),
    );
    expect(sum([BRIDGE.netRental, BRIDGE.interest, BRIDGE.taxExempt])).toBe(
      Number(BRIDGE.bookNetIncome),
    );
    expect(sum(DEPRECIATION.parts)).toBe(Number(DEPRECIATION.total));
    expect([BRIDGE.netRental, BRIDGE.bookNetIncome, DEPRECIATION.total]).toEqual([
      "1231600",
      "1256200",
      "733500",
    ]);
  });

  it("a · the draft shows its five citations and lights the cited row", async () => {
    show("a");
    const markers = Array.from(document.querySelectorAll("[data-doc='paragraph'] button"));
    expect(markers.map((b) => b.textContent.trim())).toEqual(["1", "2", "3", "4", "5"]);
    expect(screen.getByText("1,231,600")).toBeTruthy();
    const first = markers[0];
    if (first === undefined) throw new Error("no marker");
    fireEvent.pointerEnter(first);
    fireEvent.mouseEnter(first);
    await waitFor(() => {
      expect(document.querySelector("li[data-lit]")).not.toBeNull();
    });
  });

  it("b · drafting draws no memo", () => {
    show("b");
    expect(document.querySelector("[data-doc='blocks']")).toBeNull();
  });

  it("c · approved names Samuel Ito", () => {
    show("c");
    expect(screen.getByText(/Samuel Ito · Sep 14, 9:40 AM/)).toBeTruthy();
    expect(screen.getByRole<HTMLButtonElement>("button", { name: /Approved/ }).disabled).toBe(
      true,
    );
  });

  it("d · the ENG-04 letter holds template and clause blocks only", () => {
    expect(tpl10Document("d").variant).toBe("letter");
    show("d");
    expect(document.querySelector("[data-doc='letterhead']")).not.toBeNull();
    for (const section of MEMO_SECTIONS) {
      for (const p of section.paragraphs) expect(screen.queryByText(p)).toBeNull();
    }
    expect(screen.queryAllByText(/§754 election/).length).toBeGreaterThan(0);
  });
});
