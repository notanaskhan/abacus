// SPEC-021 (TASK-037): the request item detail page.
import type { ItemVersionOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { ItemDetail } from "./ItemDetail";

const E = "e1";
const I = "i1";
const ITEM: RequestItemOut = {
  id: I,
  engagement_id: E,
  description: "Trial balance at year end",
  audit_area: "General ledger",
  status: "ready_for_review",
  created_at: "2026-10-01T00:00:00Z",
  evidence_version_id: "v2",
  retrievability_tier: "A",
  client_visible: true,
  client_assignee_user_id: null,
};

function version(over: Partial<ItemVersionOut> = {}): ItemVersionOut {
  return {
    id: "v2",
    version_no: 2,
    method: "retrieved",
    source: "fake",
    period_start: "2026-01-01",
    period_end: "2026-12-31",
    pulled_at: "2026-10-09T10:00:00Z",
    created_at: "2026-10-09T10:01:00Z",
    size_bytes: 2048,
    media_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    fingerprint: "ab".repeat(32),
    file_name: null,
    uploaded_by: null,
    uploaded_by_name: "",
    decision: null,
    ...over,
  };
}

const UPLOAD = version({
  id: "v1",
  version_no: 1,
  method: "uploaded",
  source: "client_upload",
  period_start: null,
  period_end: null,
  pulled_at: null,
  file_name: "tb-final.pdf",
  uploaded_by: "u-c",
  uploaded_by_name: "Cara Client",
  media_type: "application/pdf",
  decision: {
    decision: "send_back",
    reason_code: "incomplete",
    decided_by: "u-m",
    decided_by_name: "Max Manager",
    decided_at: "2026-10-08T12:00:00Z",
  },
});

function routes(role: string, versions: ItemVersionOut[] = [version(), UPLOAD]) {
  return {
    [`GET /v1/engagements/${E}/request-items`]: () => json([ITEM]),
    [`GET /v1/engagements/${E}/request-items/${I}/versions`]: () => json(versions),
    [`GET /v1/engagements/${E}/screening-results`]: () =>
      json([
        {
          id: "s1",
          evidence_version_id: "v2",
          action: "ready_for_review",
          confidence: "0.91",
          rationale: "Totals balance; <b>bold</b> stays text.",
          citations: [
            {
              cell: "B12",
              quote: "Total debits",
              value: "125000.00",
              verified: true,
              reason: null,
            },
            { cell: "Z99", quote: null, value: null, verified: false, reason: "cell_not_found" },
          ],
          unverified: ["Suspense account cleared"],
          created_at: "2026-10-09T10:02:00Z",
        },
      ]),
    [`GET /v1/engagements/${E}`]: () =>
      json({ id: E, team: [{ user_id: "u-me", display_name: "Me", role }] }),
    "GET /v1/me": () =>
      json({
        user_id: "u-me",
        display_name: "Me",
        email: "me@dev.test",
        active_tenant_id: "t1",
        memberships: [{ tenant_id: "t1", firm_name: "Dev firm", firm_role: null, kind: "staff" }],
      }),
  };
}

const page = (): void => {
  renderRoutes([{ path: "/", component: () => <ItemDetail engagementId={E} itemId={I} /> }]);
};

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("ac1 versions with provenance", () => {
  it("lists every version newest first with how it arrived", async () => {
    mockApi(routes("staff"));
    page();
    expect(await screen.findByRole("heading", { name: "Trial balance at year end" })).toBeTruthy();
    const list = await screen.findByRole("list", { name: "Evidence versions" });
    const cards = within(list).getAllByRole("listitem");
    expect(cards[0]?.textContent).toContain("Retrieved from fake · 2026-01-01 to 2026-12-31");
    expect(cards[0]?.textContent).toContain("2 KB");
    expect(cards[0]?.textContent).toContain("abababababab");
    expect(cards[1]?.textContent).toContain("Uploaded by Cara Client");
    expect(cards[1]?.textContent).toContain("tb-final.pdf");
  });
});

describe("ac3 screening with verified citations", () => {
  it("marks each citation and shows model text as plain text with the AI tag", async () => {
    mockApi(routes("staff"));
    page();
    const citations = await screen.findByRole("list", { name: "Citations" });
    expect(within(citations).getByText("Verified")).toBeTruthy();
    expect(within(citations).getByText(/Not verified: the cited cell doesn't exist/)).toBeTruthy();
    expect(screen.getByText("AI")).toBeTruthy();
    expect(screen.getByText(/<b>bold<\/b> stays text/)).toBeTruthy();
    expect(screen.getByText("Suspense account cleared")).toBeTruthy();
  });
});

describe("ac4 decisions by right", () => {
  it("offers a manager the decision on the newest version", async () => {
    mockApi(routes("manager"));
    page();
    expect(await screen.findByRole("group", { name: /Decision on/ })).toBeTruthy();
  });

  it("shows staff the state only, and an older version's past decision", async () => {
    mockApi(routes("staff"));
    page();
    expect(await screen.findByText("Awaiting review.")).toBeTruthy();
    expect(screen.queryByRole("group", { name: /Decision on/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Version 1" }));
    expect(await screen.findByText(/by Max Manager/)).toBeTruthy();
  });
});

describe("ac2 download", () => {
  it("fetches the file with the token and saves it, and explains a failed verification", async () => {
    const created = vi.fn(() => "blob:x");
    vi.stubGlobal(
      "URL",
      Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() }),
    );
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    let first = true;
    mockApi({
      ...routes("staff"),
      [`GET /v1/engagements/${E}/evidence-versions/v2/content`]: () => {
        if (first) {
          first = false;
          return new Response("abc", {
            headers: {
              "Content-Type": "application/pdf",
              "Content-Disposition": 'attachment; filename="tb.pdf"',
            },
          });
        }
        return json({ detail: "integrity_failed" }, 409);
      },
    });
    page();
    const list = await screen.findByRole("list", { name: "Evidence versions" });
    const download = within(list).getAllByRole("button", { name: "Download" })[0] as HTMLElement;
    fireEvent.click(download);
    await waitFor(() => {
      expect(click).toHaveBeenCalled();
    });
    fireEvent.click(download);
    expect(await screen.findByText("This file couldn't be verified.")).toBeTruthy();
  });
});

describe("ac5 ac6 states", () => {
  it("says not allowed when the evidence is refused", async () => {
    mockApi({
      ...routes("staff"),
      [`GET /v1/engagements/${E}/request-items/${I}/versions`]: () =>
        json({ detail: "forbidden" }, 403),
    });
    page();
    expect(await screen.findByText("Not allowed")).toBeTruthy();
  });

  it("shows the empty state for an item without evidence", async () => {
    mockApi(routes("staff", []));
    page();
    expect(await screen.findByText("No evidence yet")).toBeTruthy();
  });
});
