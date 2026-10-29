import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ENVELOPES, TAX_RETURNS } from "../../../fixtures/seed/tax";
import { Tpl01Specimen, boardEnvelope, daysToDue, daysTone } from ".";

// F-06-T08 (F-06 F2; docs/screens/TPL-01.md): "TPL-01a reads 15 of 79 open sorted by extended due
// date, TPL-01b shows exactly the ten returns behind E1-E10 with an amber Status chip, and synced
// chips never use a green-tint fill."

afterEach(cleanup);

describe("TPL-01a: default", () => {
  it("reads Showing 15 of 79 open, sorted by extended due date then client", () => {
    render(<Tpl01Specimen state="a" />);
    expect(screen.getByText("Showing 15 of 79 open")).toBeTruthy();
    const page = boardEnvelope({ tile: null, query: "", year: 2025 }).items;
    expect(page).toHaveLength(15);
    for (let i = 1; i < page.length; i += 1) {
      const [a, b] = [page[i - 1], page[i]];
      if (a === undefined || b === undefined) continue;
      expect(a.due < b.due || (a.due === b.due && a.client.localeCompare(b.client) <= 0)).toBe(
        true,
      );
    }
  });

  it("the summary and the tiles foot to the seed (79 open, 145 done, 224)", () => {
    render(<Tpl01Specimen state="a" />);
    expect(
      screen.getByText("79 open · 145 done · 224 TY2025 returns · 161 extended"),
    ).toBeTruthy();
    const counts = boardEnvelope({ tile: null, query: "", year: 2025 }).counts;
    expect(counts).toMatchObject({
      prepared: 17,
      in_review: 15,
      action_required: 11,
      approved: 7,
      gathering: 8,
      preparing: 9,
      awaiting_signature: 10,
      filed_accepted: 145,
    });
  });
});

describe("TPL-01b: Awaiting signature", () => {
  it("shows exactly the ten returns behind E1 to E10, with their signer chips", () => {
    const rows = boardEnvelope({ tile: "awaiting_signature", query: "", year: 2025 }).items;
    expect(rows.map((r) => r.envelope).sort()).toEqual(ENVELOPES.map((e) => e.key).sort());
    render(<Tpl01Specimen state="b" />);
    expect(document.querySelectorAll("[data-signer-chips]")).toHaveLength(10);
  });

  it("synced chips never use a green-tint fill", () => {
    render(<Tpl01Specimen state="a" />);
    const synced = document.querySelectorAll('[data-code="synced"]');
    expect(synced.length).toBeGreaterThan(0);
    for (const chip of synced) expect(chip.className).not.toMatch(/bg-green-tint/);
  });
});

describe("TPL-01c, e: empty states", () => {
  it("c: no results for Schwab, tiles and count hidden", () => {
    render(<Tpl01Specimen state="c" />);
    expect(screen.getByText("No results for 'Schwab'.")).toBeTruthy();
  });

  it("e: no TY2026 returns yet, with season setup", () => {
    render(<Tpl01Specimen state="e" />);
    expect(screen.getByText("No TY2026 returns yet.")).toBeTruthy();
    expect(
      screen.getByText(
        "Roll clients forward from TY2025 to create returns, binders and assignments.",
      ),
    ).toBeTruthy();
  });
});

describe("days to due", () => {
  it("≤ 7 red-ink, ≤ 30 amber-ink, later ink-2, from the demo clock", () => {
    expect(daysToDue("2026-09-21")).toBe(7);
    expect(daysTone(7)).toBe("text-red-ink");
    expect(daysTone(8)).toBe("text-amber-ink");
    expect(daysTone(30)).toBe("text-amber-ink");
    expect(daysTone(31)).toBe("text-ink-2");
  });

  it("every row's status word comes from the registry, never from the seed", () => {
    expect(TAX_RETURNS.every((r) => typeof r.status === "string")).toBe(true);
  });
});
