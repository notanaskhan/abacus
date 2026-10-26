// SPEC-035 AC-4, AC-8 (TASK-073): the firm reviews drafts (AI tag, edit, approve, discard, bulk
// approval only after confirming it read them) and sees approved drafted guidance labelled.
import type { GuidanceDraftOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { GuidanceDrafts, sourceLabel } from "./GuidanceDrafts";

const E = "e1";
const BASE = `/v1/engagements/${E}`;
const ITEMS = [
  { id: "i1", description: "Lease agreements", status: "requested" },
  { id: "i2", description: "Board minutes", status: "requested" },
].map((i) => ({
  ...i,
  engagement_id: E,
  audit_area: "General",
  created_at: "2026-10-01T00:00:00Z",
})) as RequestItemOut[];

function draft(id: string, item: string): GuidanceDraftOut {
  return {
    id,
    request_item_id: item,
    why: "To understand the company's lease commitments.",
    good_looks_like: "Every lease in effect at the year-end date, signed copies as PDFs.",
    effort: "medium",
    effort_reason: "Several agreements to gather",
    created_at: "2026-10-15T10:00:00Z",
  };
}

function panel(
  drafts: GuidanceDraftOut[],
  extra = {},
): { calls: { method: string; path: string; body: unknown }[] } {
  const api = mockApi({ [`GET ${BASE}/guidance-drafts`]: () => json(drafts), ...extra });
  renderRoutes([
    { path: "/", component: () => <GuidanceDrafts engagementId={E} items={ITEMS} canDraft /> },
  ]);
  return api;
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

describe("ac4 review", () => {
  it("shows each draft beside its request and approves it as drafted", async () => {
    const { calls } = panel([draft("d1", "i1")], {
      [`POST ${BASE}/guidance-drafts/approve`]: () => json({ decided: 1 }, 201),
    });
    const list = await screen.findByRole("list", { name: "Drafts to review" });
    expect(within(list).getByText("Lease agreements")).toBeTruthy();
    expect(within(list).getByText(/Suggested effort: medium/)).toBeTruthy();
    fireEvent.click(within(list).getByRole("button", { name: "Approve" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/approve"))?.body).toEqual({
        approvals: [{ draft_id: "d1", why: null, good_looks_like: null }],
      });
    });
  });

  it("sends the edited text when approving an edit", async () => {
    const { calls } = panel([draft("d1", "i1")], {
      [`POST ${BASE}/guidance-drafts/approve`]: () => json({ decided: 1 }, 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Why we need it"), {
      target: { value: "Edited why." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve edited" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/approve"))?.body).toMatchObject({
        approvals: [{ draft_id: "d1", why: "Edited why." }],
      });
    });
  });

  it("approves several only after confirming each was read", async () => {
    const { calls } = panel([draft("d1", "i1"), draft("d2", "i2")], {
      [`POST ${BASE}/guidance-drafts/approve`]: () => json({ decided: 2 }, 201),
    });
    const all = await screen.findByRole("button", { name: "Approve all 2" });
    expect((all as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("I've read each draft above"));
    fireEvent.click(all);
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/approve"))?.body).toMatchObject({
        confirmed_read: true,
      });
    });
  });

  it("explains a refused edit", async () => {
    panel([draft("d1", "i1")], {
      [`POST ${BASE}/guidance-drafts/approve`]: () =>
        json({ detail: "edited_draft_refused" }, 422),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByText(/remove amounts, dates, names/)).toBeTruthy();
  });
});

describe("ac8 states and labels", () => {
  it("shows nothing for roles that can't draft", () => {
    mockApi({});
    const { container } = renderRoutes([
      {
        path: "/",
        component: () => <GuidanceDrafts engagementId={E} items={ITEMS} canDraft={false} />,
      },
    ]);
    expect(container.textContent).toBe("");
  });

  it("labels approved drafted guidance for the firm", () => {
    expect(
      sourceLabel({ ...ITEMS[0], guidance_source: "drafted" } as RequestItemOut, "Dana Leader"),
    ).toBe("Drafted via Agent, approved by Dana Leader");
  });
});
