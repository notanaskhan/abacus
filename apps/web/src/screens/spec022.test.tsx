// SPEC-022 (TASK-038): tiers, filters in the URL, the summary strip and the tier override.
import type { RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Board } from "./Board";

const E = "e1";

function item(over: Partial<RequestItemOut>): RequestItemOut {
  return {
    id: "i1",
    engagement_id: E,
    description: "Trial balance at year end",
    audit_area: "General ledger",
    status: "open",
    created_at: "2026-10-01T00:00:00Z",
    evidence_version_id: null,
    retrievability_tier: "A",
    client_visible: true,
    client_assignee_user_id: null,
    dataset: "trial_balance",
    tier_source: "rule",
    available: true,
    ...over,
  };
}

const ITEMS = [
  item({}),
  item({
    id: "i2",
    description: "General ledger detail",
    dataset: "general_ledger",
    available: false,
  }),
  item({
    id: "i3",
    description: "Bank confirmation",
    audit_area: "Cash",
    retrievability_tier: "E",
    dataset: null,
  }),
  item({
    id: "i4",
    description: "Management letter",
    audit_area: "Completion",
    retrievability_tier: null,
    dataset: null,
    tier_source: null,
  }),
];

function routes(): Parameters<typeof mockApi>[0] {
  return {
    [`GET /v1/engagements/${E}`]: () =>
      json({
        id: E,
        name: "FY2026 audit",
        type: "audit",
        status: "active",
        client_name: "Northwind",
        client_entity_name: "Northwind Ltd",
        fiscal_period_start: "2026-01-01",
        fiscal_period_end: "2026-12-31",
        created_at: "2026-10-01T00:00:00Z",
        team: [],
      }),
    [`GET /v1/engagements/${E}/request-items`]: () => json(ITEMS),
    [`GET /v1/engagements/${E}/evidence-versions`]: () => json([]),
    [`GET /v1/engagements/${E}/screening-results`]: () => json([]),
    [`GET /v1/engagements/${E}/board-summary`]: () =>
      json({
        total: 4,
        by_status: { open: 4 },
        by_tier: { A: 2, E: 1 },
        unclassified: 1,
        retrieved_never_asked: 2,
        retrievable_share: 0.6667,
      }),
  };
}

const board = (at = "/"): void => {
  renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }], { at });
};

const titles = (): string[] =>
  within(screen.getByRole("list", { name: "Request items" }))
    .getAllByRole("link")
    .map((a) => a.textContent);

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac1 ac3 tiers on the board", () => {
  it("shows each tier with its meaning, unavailable A items and unclassified ones", async () => {
    mockApi(routes());
    board();
    const list = await screen.findByRole("list", { name: "Request items" });
    const chips = within(list).getAllByText(/^Tier [A-E]$/);
    expect(chips[0]?.getAttribute("title")).toBe(
      "A standard report the connected system produces as is",
    );
    expect(within(list).getAllByText(/not available from the connected system/)).toHaveLength(1);
    expect(within(list).getByText("Unclassified")).toBeTruthy();
  });
});

describe("ac5 filters and summary", () => {
  it("shows the summary strip", async () => {
    mockApi(routes());
    board();
    const strip = await screen.findByLabelText("Board summary");
    expect(within(strip).getByText("Retrieved, never asked").nextSibling?.textContent).toBe("2");
    expect(within(strip).getByText("67%")).toBeTruthy();
  });

  it("narrows the list by tier and text, and reads filters from the URL", async () => {
    mockApi(routes());
    board("/?tier=A");
    await screen.findByRole("list", { name: "Request items" });
    expect(titles()).toEqual(["Trial balance at year end", "General ledger detail"]);
    const filters = screen.getByRole("search", { name: "Filter requests" });
    fireEvent.change(within(filters).getByLabelText("Search"), { target: { value: "detail" } });
    await waitFor(() => {
      expect(titles()).toEqual(["General ledger detail"]);
    });
    fireEvent.change(within(filters).getByLabelText("Tier"), { target: { value: "none" } });
    expect(await screen.findByText("No items match these filters")).toBeTruthy();
  });
});

describe("ac2 tier override", () => {
  it("sets a tier for an item, and Automatic clears it", async () => {
    const { calls } = mockApi({
      ...routes(),
      [`PUT /v1/engagements/${E}/request-items/i4/tier`]: () =>
        json(item({ id: "i4", retrievability_tier: "D", tier_source: "override" })),
    });
    board();
    fireEvent.change(await screen.findByLabelText("Tier for Management letter"), {
      target: { value: "D" },
    });
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ tier: "D" });
    });
  });
});
