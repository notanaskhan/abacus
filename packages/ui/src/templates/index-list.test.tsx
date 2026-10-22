import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IndexList, type IndexColumn, type IndexListProps, type ListEnvelope } from "./index-list";

// F-05-T28 acceptance: "T1a to T1e render from typed view models, tiles never count themselves
// out, and T1c hides tiles and the count." Data from the T1 handoff (TY2025 returns).

interface Return {
  id: string;
  client: string;
  form: string;
  status: string;
  team: string;
}

const COLUMNS: IndexColumn<Return>[] = [
  { key: "client", header: "Client", cell: (r) => r.client },
  { key: "form", header: "Form", width: 80, cell: (r) => r.form },
  { key: "status", header: "Status", width: 180, cell: (r) => r.status },
  { key: "team", header: "Preparer / Reviewer", width: 150, cell: (r) => r.team },
];

const TILES = [
  { code: "prepared", label: "Prepared", variant: "state" as const },
  { code: "in_review", label: "In review", variant: "amber" as const },
  { code: "issues", label: "Issues", variant: "red-tint" as const },
  { code: "ready", label: "Ready", variant: "green-tint" as const },
];

const PREPARER = {
  key: "preparer",
  label: "Preparer",
  icon: "user" as const,
  placeholder: "Anyone",
  options: [
    { value: "ko", label: "Kevin Osei" },
    { value: "pr", label: "Priya Raman" },
  ],
};

const T1A: ListEnvelope<Return> = {
  items: [
    {
      id: "feld",
      client: "Jonah & Claire Feld",
      form: "1040",
      status: "In review",
      team: "KO / SI",
    },
    {
      id: "cl",
      client: "Copperleaf Coffee Roasters, Inc.",
      form: "1120-S",
      status: "Issues",
      team: "KO / SI",
    },
  ],
  next_cursor: "c2",
  total: 79,
  counts: { prepared: 17, in_review: 15, issues: 11, ready: 7 },
};

function list(props: Partial<IndexListProps<Return>> = {}) {
  return render(
    <IndexList<Return>
      title="Tax Returns"
      noun="returns"
      state={{ kind: "ready" }}
      envelope={T1A}
      columns={COLUMNS}
      rowKey={(r) => r.id}
      chips={[{ ...PREPARER, value: null }]}
      tiles={TILES}
      newLabel="New Return…"
      empty={{ title: "No returns yet", body: "Returns appear here once a client is set up." }}
      {...props}
    />,
  );
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("T1a default", () => {
  it("shows the count from the envelope's total, the tiles, the title and New", () => {
    list({ selected: "feld" });
    expect(screen.getByText("Showing 2 of 79")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Tax Returns" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /New Return…/ })).toBeTruthy();
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Client",
      "Form",
      "Status",
      "Preparer / Reviewer",
    ]);
    const feld = screen.getByText("Jonah & Claire Feld").closest("tr");
    expect(feld?.getAttribute("aria-selected")).toBe("true");
    expect(feld?.className).toContain("h-[38px]");
  });

  it("selects on click and opens on double click", () => {
    const onSelect = vi.fn();
    const onOpen = vi.fn();
    list({ onSelect, onOpen });
    const row = screen.getByText("Copperleaf Coffee Roasters, Inc.").closest("tr");
    if (row === null) throw new Error("row");
    fireEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith(T1A.items[1]);
    fireEvent.doubleClick(row);
    expect(onOpen).toHaveBeenCalledWith(T1A.items[1]);
  });

  it("a row with a second line is 44 high", () => {
    list({ twoLine: (r) => r.id === "cl" });
    expect(
      screen.getByText("Copperleaf Coffee Roasters, Inc.").closest("tr")?.className,
    ).toContain("h-[44px]");
  });
});

describe("T1b filtered: tiles never count themselves out", () => {
  it("shows the server's counts, not the rows on screen", () => {
    // The Issues tile and the Preparer chip are set: 2 rows show, yet every tile keeps the
    // count the server computed over the filters minus the tile.
    const filtered: ListEnvelope<Return> = {
      items: [
        {
          id: "cl",
          client: "Copperleaf Coffee Roasters, Inc.",
          form: "1120-S",
          status: "Issues",
          team: "KO / SI",
        },
        {
          id: "em",
          client: "Ellison & Ruth Marsh",
          form: "1040",
          status: "Issues",
          team: "KO / SI",
        },
      ],
      next_cursor: null,
      total: 11,
      counts: { prepared: 17, in_review: 15, issues: 11, ready: 7 },
    };
    list({
      envelope: filtered,
      tile: "issues",
      chips: [{ ...PREPARER, value: "ko" }],
      onClear: () => undefined,
    });
    const tiles = within(screen.getByRole("group", { name: "Status" }));
    for (const [label, n] of [
      ["Prepared", "17"],
      ["In review", "15"],
      ["Issues", "11"],
      ["Ready", "7"],
    ] as const) {
      expect(tiles.getByRole("button", { name: new RegExp(label) }).textContent).toContain(n);
    }
    expect(tiles.getByRole("button", { name: /Issues/ }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByText("Showing 2 of 11")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
  });

  it("a tile filters by its code, and pressing it again clears it", () => {
    const onTile = vi.fn();
    const { rerender } = list({ onTile });
    fireEvent.click(screen.getByRole("button", { name: /Issues/ }));
    expect(onTile).toHaveBeenLastCalledWith("issues");
    rerender(
      <IndexList<Return>
        title="Tax Returns"
        noun="returns"
        state={{ kind: "ready" }}
        envelope={T1A}
        columns={COLUMNS}
        rowKey={(r) => r.id}
        tiles={TILES}
        tile="issues"
        onTile={onTile}
        empty={{ title: "No returns yet" }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Issues/ }));
    expect(onTile).toHaveBeenLastCalledWith(null);
  });

  it("no Clear while nothing filters", () => {
    list({ onClear: () => undefined });
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
  });
});

describe("T1c empty", () => {
  it("hides the tiles and the count, and offers one secondary button", () => {
    list({
      state: { kind: "empty", action: { label: "Add a client", onSelect: () => undefined } },
      envelope: { items: [], next_cursor: null, total: 0, counts: {} },
    });
    expect(screen.queryByRole("group", { name: "Status" })).toBeNull();
    expect(screen.queryByText(/Showing/)).toBeNull();
    expect(screen.getByText("No returns yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add a client" })).toBeTruthy();
    // Header and column heads stay.
    expect(screen.getByRole("heading", { name: "Tax Returns" })).toBeTruthy();
    expect(screen.getAllByRole("columnheader").length).toBeGreaterThan(0);
  });
});

describe("T1d filtered, no results", () => {
  it("says so and offers Clear filters", () => {
    const clear = vi.fn();
    list({
      state: { kind: "filtered-empty", query: "Haverford", clear },
      envelope: {
        items: [],
        next_cursor: null,
        total: 0,
        counts: { prepared: 0, in_review: 0, issues: 0, ready: 0 },
      },
      query: "Haverford",
    });
    expect(screen.getByText("No results for ‘Haverford’.")).toBeTruthy();
    fireEvent.click(screen.getByText("Clear filters"));
    expect(clear).toHaveBeenCalledOnce();
  });
});

describe("T1e loading", () => {
  it("keeps the header and column heads, and shows 8 skeleton rows", () => {
    const { container } = list({ state: { kind: "loading" }, envelope: undefined });
    expect(screen.getByRole("heading", { name: "Tax Returns" })).toBeTruthy();
    expect(screen.getAllByRole("columnheader").length).toBe(4);
    act(() => {
      vi.advanceTimersByTime(250);
    });
    const skeleton = container.querySelector("[data-skeleton]");
    expect(skeleton).not.toBeNull();
    expect(skeleton?.querySelectorAll("[data-row]").length).toBe(8);
    expect(screen.queryByText(/Showing/)).toBeNull();
  });
});
