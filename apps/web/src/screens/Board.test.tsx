import type {
  EngagementOut,
  EvidenceVersionOut,
  RequestItemOut,
  RetrievalOut,
  ScreeningResultOut,
} from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  json,
  mockApi,
  never,
  signInForTest,
  renderRoutes,
  type Handler,
} from "../testing/support";
import { Board } from "./Board";

const E = "e1";
const BASE = `/v1/engagements/${E}`;

const engagement: EngagementOut = {
  id: E,
  name: "FY25 audit",
  client_name: "Acme",
  client_entity_name: "Acme Holdings",
  fiscal_period_start: "2025-01-01",
  fiscal_period_end: "2025-12-31",
  status: "active",
  type: "audit",
  created_at: "2025-01-02T00:00:00Z",
  team: [],
};

function item(over: Partial<RequestItemOut> = {}): RequestItemOut {
  return {
    id: "i1",
    engagement_id: E,
    description: "Trial balance",
    audit_area: "Financial reporting",
    status: "received",
    evidence_version_id: "v1",
    created_at: "2025-01-03T00:00:00Z",
    ...over,
  };
}

const version: EvidenceVersionOut = {
  id: "v1",
  evidence_item_id: "ev1",
  version_no: 1,
  method: "retrieved",
  source: "fake",
  pulled_at: "2025-01-04T00:00:00Z",
  period_start: "2025-01-01",
  period_end: "2025-12-31",
  created_at: "2025-01-04T00:00:00Z",
};

function screening(over: Partial<ScreeningResultOut> = {}): ScreeningResultOut {
  return {
    id: "s1",
    evidence_version_id: "v1",
    action: "ready_for_review",
    confidence: "0.900",
    rationale: "Totals agree with the ledger.",
    citations: [
      { cell: "A1", quote: "Cash 100", value: "100.00", verified: true, reason: null },
      { cell: "B2", quote: "Receivables", value: null, verified: false, reason: "quote_mismatch" },
    ],
    unverified: ["Could not confirm the closing balance"],
    created_at: "2025-01-05T00:00:00Z",
    ...over,
  };
}

function api(
  over: {
    items?: RequestItemOut[];
    versions?: EvidenceVersionOut[];
    results?: ScreeningResultOut[];
  } & Record<
    string,
    Handler | RequestItemOut[] | EvidenceVersionOut[] | ScreeningResultOut[]
  > = {},
): ReturnType<typeof mockApi> {
  const { items, versions, results, ...handlers } = over;
  return mockApi({
    [`GET ${BASE}`]: () => json(engagement),
    [`GET ${BASE}/request-items`]: () => json(items ?? [item()]),
    [`GET ${BASE}/evidence-versions`]: () => json(versions ?? [version]),
    [`GET ${BASE}/screening-results`]: () => json(results ?? [screening()]),
    ...(handlers as Record<string, Handler>),
  });
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac18 Board screen", () => {
  it("shows the engagement and the item with status, source and screening result", async () => {
    api();
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    expect(await screen.findByRole("heading", { name: "FY25 audit" })).toBeTruthy();
    expect(screen.getByText("Trial balance")).toBeTruthy();
    expect(screen.getByText("Financial reporting")).toBeTruthy();
    expect(screen.getByText("Received")).toBeTruthy();
    expect(screen.getByText("Retrieved · version 1")).toBeTruthy();
    expect(screen.getByText(/Agent proposes/)).toBeTruthy();
    expect(screen.getByText("Ready for review")).toBeTruthy();
    expect(screen.getByText(/90%/)).toBeTruthy();
    expect(screen.getByText("Totals agree with the ledger.")).toBeTruthy();
  });

  it("marks citations Verified or Unverified and lists the unverified notes", async () => {
    api();
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    const citations = await screen.findByRole("list", { name: "Citations" });
    const rows = within(citations).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[0] as HTMLElement).getByText("Verified")).toBeTruthy();
    expect(within(rows[1] as HTMLElement).getByText("Unverified")).toBeTruthy();
    expect(screen.getByText("Could not confirm the closing balance")).toBeTruthy();
  });

  it("shows a hostile rationale, quote and note as text only", async () => {
    const hostile = '<img src=x onerror="alert(1)">';
    api({
      results: [
        screening({
          rationale: `${hostile}‮reversed https://evil.test/pay`,
          citations: [
            {
              cell: "A1",
              quote: "<script>alert(2)</script>",
              value: null,
              verified: true,
              reason: null,
            },
          ],
          unverified: ["<b>bold</b> note"],
        }),
      ],
    });
    const { container } = renderRoutes([
      { path: "/", component: () => <Board engagementId={E} /> },
    ]);
    await screen.findByText(/reversed https:\/\/evil.test\/pay/);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("a[href*='evil']")).toBeNull();
    expect(container.textContent).toContain(hostile);
    expect(container.textContent).toContain("<script>alert(2)</script>");
    expect(container.textContent).not.toContain("‮");
  });

  it("shows Screening… when evidence has no result yet", async () => {
    api({ results: [] });
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    await screen.findByText("Retrieved · version 1");
    expect(screen.getByRole("status").textContent).toContain("Screening…");
    expect(screen.queryByText(/Agent proposes/)).toBeNull();
  });

  it("shows no screening for an item without evidence", async () => {
    api({
      items: [item({ status: "open", evidence_version_id: null })],
      versions: [],
      results: [],
    });
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    expect(await screen.findByText("No evidence yet")).toBeTruthy();
    expect(screen.queryByText("Screening…")).toBeNull();
    expect(screen.getByText("Open")).toBeTruthy();
  });

  it("shows a busy skeleton while loading", async () => {
    api({ [`GET ${BASE}/request-items`]: never });
    const { container } = renderRoutes([
      { path: "/", component: () => <Board engagementId={E} /> },
    ]);
    await waitFor(() => {
      expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
    });
  });

  it("shows an alert with Retry when a read fails", async () => {
    let attempts = 0;
    api({
      [`GET ${BASE}/screening-results`]: () => {
        attempts += 1;
        return attempts === 1 ? json({ detail: "Down" }, 500) : json([screening()]);
      },
    });
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Couldn't load the evidence board");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Totals agree with the ledger.")).toBeTruthy();
  });

  it("shows the empty state when there are no request items", async () => {
    api({ items: [], versions: [], results: [] });
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    expect(await screen.findByText("No request items yet")).toBeTruthy();
  });

  it("adds a request item and reloads the list", async () => {
    let added = false;
    const { calls } = api({
      [`GET ${BASE}/request-items`]: () =>
        json(added ? [item({ evidence_version_id: null })] : []),
      [`POST ${BASE}/request-items`]: () => {
        added = true;
        return json(item({ evidence_version_id: null }), 201);
      },
    });
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    await screen.findByText("No request items yet");
    fireEvent.change(screen.getByLabelText("Request"), { target: { value: "Trial balance" } });
    fireEvent.change(screen.getByLabelText("Audit area"), {
      target: { value: "Financial reporting" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add request item" }));
    expect(await screen.findByText("Financial reporting")).toBeTruthy();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({
      description: "Trial balance",
      audit_area: "Financial reporting",
    });
  });

  it("retrieves the trial balance for the engagement's fiscal period, disabled while running", async () => {
    const run: RetrievalOut = {
      sync_run_id: "r1",
      request_item_id: "i1",
      status: "running",
      started_at: "2025-01-06T00:00:00Z",
      finished_at: null,
      evidence_version_id: null,
      failure_code: null,
      queued_reason: null,
      estimated_start_at: null,
    };
    const { calls } = api({
      items: [item({ status: "open", evidence_version_id: null })],
      versions: [],
      results: [],
      [`POST ${BASE}/retrievals`]: () => json(run, 202),
      [`GET ${BASE}/retrievals/r1`]: () => json(run),
    });
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    const button = await screen.findByRole("button", { name: "Retrieve trial balance" });
    expect(button.hasAttribute("disabled")).toBe(false);
    fireEvent.click(button);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Retrieve trial balance" }).hasAttribute("disabled"),
      ).toBe(true);
    });
    const post = calls.find((c) => c.method === "POST");
    expect(post?.path).toBe(`${BASE}/retrievals`);
    expect(post?.body).toEqual({
      request_item_id: "i1",
      period_start: "2025-01-01",
      period_end: "2025-12-31",
    });
    expect(screen.getByText("Retrieving…")).toBeTruthy();
  });

  describe("a retrieval waiting for capacity (SPEC-003 AC-13, TASK-018 018b)", () => {
    function queuedRun(over: Partial<RetrievalOut> = {}): RetrievalOut {
      return {
        sync_run_id: "r1",
        request_item_id: "i1",
        status: "queued",
        started_at: "2025-01-06T00:00:00Z",
        finished_at: null,
        evidence_version_id: null,
        failure_code: null,
        queued_reason: "firm_cap",
        estimated_start_at: null,
        ...over,
      };
    }

    function openItemApi(get: () => Response | Promise<Response>): ReturnType<typeof mockApi> {
      return api({
        items: [item({ status: "open", evidence_version_id: null })],
        versions: [],
        results: [],
        [`POST ${BASE}/retrievals`]: () => json(queuedRun(), 202),
        [`GET ${BASE}/retrievals/r1`]: get,
      });
    }

    async function startRetrieval(): Promise<void> {
      renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
      fireEvent.click(await screen.findByRole("button", { name: "Retrieve trial balance" }));
    }

    it("says Queued with the expected time when there is an estimate, and keeps Retrieve disabled", async () => {
      openItemApi(() => json(queuedRun({ estimated_start_at: "2025-01-06T09:30:00Z" })));
      await startRetrieval();
      const expected = new Date("2025-01-06T09:30:00Z").toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      expect(await screen.findByText(`Queued: expected to start by ${expected}`)).toBeTruthy();
      expect(
        screen.getByRole("button", { name: "Retrieve trial balance" }).hasAttribute("disabled"),
      ).toBe(true);
      expect(screen.queryByText("Retrieving…")).toBeNull();
    });

    it("says Queued: waiting for capacity when the estimate is unknown", async () => {
      openItemApi(() => json(queuedRun()));
      await startRetrieval();
      expect(await screen.findByText("Queued: waiting for capacity")).toBeTruthy();
      expect(screen.queryByText("Retrieving…")).toBeNull();
      expect(
        screen.getByRole("button", { name: "Retrieve trial balance" }).hasAttribute("disabled"),
      ).toBe(true);
    });

    it("never names the reason or another firm", async () => {
      const { container } = (() => {
        openItemApi(() => json(queuedRun({ queued_reason: "firm_cap" })));
        return renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
      })();
      fireEvent.click(await screen.findByRole("button", { name: "Retrieve trial balance" }));
      await screen.findByText(/^Queued:/);
      expect(container.textContent).not.toContain("firm_cap");
    });

    it("keeps polling while queued, then ends and enables Retrieve again", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      try {
        let reads = 0;
        const { calls } = openItemApi(() => {
          reads += 1;
          return json(
            reads < 3
              ? queuedRun()
              : queuedRun({
                  status: "succeeded",
                  queued_reason: null,
                  finished_at: "2025-01-06T00:01:00Z",
                  evidence_version_id: "v1",
                }),
          );
        });
        await startRetrieval();
        await screen.findByText("Queued: waiting for capacity");
        const polls = (): number => calls.filter((c) => c.path === `${BASE}/retrievals/r1`).length;
        const before = polls();
        await vi.advanceTimersByTimeAsync(2_100);
        expect(polls()).toBeGreaterThan(before); // a queued run is still polled
        await vi.advanceTimersByTimeAsync(6_000);
        await waitFor(() => {
          expect(screen.queryByText(/^Queued:/)).toBeNull();
        });
        await waitFor(() => {
          expect(
            screen
              .getByRole("button", { name: "Retrieve trial balance" })
              .hasAttribute("disabled"),
          ).toBe(false);
        });
      } finally {
        vi.useRealTimers();
      }
    });

    it("shows a failed capacity_timeout run as ended, not as queued", async () => {
      openItemApi(() =>
        json(
          queuedRun({
            status: "failed",
            failure_code: "capacity_timeout",
            queued_reason: null,
            finished_at: "2025-01-06T00:02:00Z",
          }),
        ),
      );
      await startRetrieval();
      expect(await screen.findByText("Retrieval failed. Try again.")).toBeTruthy();
      expect(screen.queryByText(/^Queued:/)).toBeNull();
      expect(screen.queryByText("Retrieving…")).toBeNull();
      expect(
        screen.getByRole("button", { name: "Retrieve trial balance" }).hasAttribute("disabled"),
      ).toBe(false);
    });
  });

  it("shows a hostile citation cell and value as text only", async () => {
    api({
      results: [
        screening({
          citations: [
            {
              cell: "<img src=x onerror=alert(1)>",
              quote: null,
              value: "<b>1,000</b>‮",
              verified: true,
              reason: null,
            },
          ],
        }),
      ],
    });
    const { container } = renderRoutes([
      { path: "/", component: () => <Board engagementId={E} /> },
    ]);
    await screen.findByText(/<b>1,000<\/b>/);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
    expect(container.textContent).not.toContain("‮");
  });

  it("disables Retrieve from the click, before any response arrives", async () => {
    api({
      items: [item({ status: "open", evidence_version_id: null })],
      versions: [],
      results: [],
      [`POST ${BASE}/retrievals`]: never,
    });
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    const button = await screen.findByRole("button", { name: "Retrieve trial balance" });
    fireEvent.click(button);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Retrieve trial balance" }).hasAttribute("disabled"),
      ).toBe(true);
    });
    expect(screen.getByText("Retrieving…")).toBeTruthy();
  });

  it("stops polling for screening after two minutes and offers Check again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { calls } = api({ results: [] });
      renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
      await screen.findByText("Retrieved · version 1");
      expect(screen.queryByText("Screening hasn't finished.")).toBeNull();
      await vi.advanceTimersByTimeAsync(125_000);
      expect(await screen.findByText("Screening hasn't finished.")).toBeTruthy();
      const reads = (): number =>
        calls.filter((c) => c.path === `${BASE}/screening-results`).length;
      const before = reads();
      await vi.advanceTimersByTimeAsync(30_000);
      expect(reads()).toBe(before);
      fireEvent.click(screen.getByRole("button", { name: "Check again" }));
      await waitFor(() => {
        expect(reads()).toBeGreaterThan(before);
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps polling for screening within the first two minutes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { calls } = api({ results: [] });
      renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
      await screen.findByText("Retrieved · version 1");
      const reads = (): number =>
        calls.filter((c) => c.path === `${BASE}/screening-results`).length;
      const before = reads();
      await vi.advanceTimersByTimeAsync(10_000);
      await waitFor(() => {
        expect(reads()).toBeGreaterThan(before);
      });
      expect(screen.queryByText("Screening hasn't finished.")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("offers nothing that accepts, approves, rejects or waives an agent proposal", async () => {
    api();
    renderRoutes([{ path: "/", component: () => <Board engagementId={E} /> }]);
    await screen.findByText(/Agent proposes/);
    expect(
      screen.queryAllByRole("button", { name: /accept|approve|reject|waive|confirm|sign.?off/i }),
    ).toHaveLength(0);
    expect(
      screen.queryAllByRole("link", { name: /accept|approve|reject|waive|confirm/i }),
    ).toHaveLength(0);
  });
});
