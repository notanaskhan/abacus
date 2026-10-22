// SPEC-035 Q3, AC-4, AC-8 (TASK-074): a firm admin or practice leader reviews drafts on a
// template version (AI tag, approve, bulk only after confirming it read them), publishes the
// approved ones as a new version, and is asked to confirm it's them when publishing needs it.
import type { TemplateDraftOut, TemplateItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { TemplateGuidanceDrafts } from "./TemplateGuidanceDrafts";

const V = "v1";
const BASE = `/v1/methodology/versions/${V}`;
const ITEMS: TemplateItemOut[] = [
  { area_code: "CASH", description: "Bank statements for all accounts", tier: "B" },
  { area_code: "LEASE", description: "Lease agreements", tier: "C" },
];

function draft(id: string, position: number, status: "pending" | "approved"): TemplateDraftOut {
  return {
    id,
    position,
    why: "To understand the company's commitments.",
    good_looks_like: "Signed copies of every agreement in effect, as PDFs.",
    effort: "medium",
    created_at: "2026-10-15T10:00:00Z",
    status,
  };
}

function panel(
  drafts: TemplateDraftOut[] | (() => Response),
  extra = {},
): { calls: { method: string; path: string; body: unknown }[] } {
  const api = mockApi({
    [`GET ${BASE}/guidance-drafts`]: typeof drafts === "function" ? drafts : () => json(drafts),
    ...extra,
  });
  renderRoutes([
    { path: "/", component: () => <TemplateGuidanceDrafts versionId={V} items={ITEMS} /> },
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

describe("ac4 review on a template", () => {
  it("shows each draft beside its standard request and approves it", async () => {
    const { calls } = panel([draft("d1", 1, "pending")], {
      [`POST ${BASE}/guidance-drafts/approve`]: () => json({ decided: 1 }, 201),
    });
    const list = await screen.findByRole("list", { name: "Template drafts" });
    expect(within(list).getByText("Lease agreements")).toBeTruthy();
    expect(within(list).getByText("AI")).toBeTruthy();
    fireEvent.click(within(list).getByRole("button", { name: "Approve" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/approve"))?.body).toEqual({
        approvals: [{ draft_id: "d1", why: null, good_looks_like: null }],
      });
    });
  });

  it("approves several only after confirming each was read", async () => {
    const { calls } = panel([draft("d1", 0, "pending"), draft("d2", 1, "pending")], {
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

  it("drafts for the items without guidance", async () => {
    const { calls } = panel([], {
      [`POST ${BASE}/draft-guidance`]: () => json({ positions: [0, 1] }, 202),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Draft guidance (2 without)" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/draft-guidance"))).toBe(true);
    });
  });
});

describe("d2 publishing", () => {
  it("publishes approved drafts as a new version", async () => {
    const { calls } = panel([draft("d1", 1, "approved")], {
      [`POST ${BASE}/publish-drafted`]: () => json({ version_id: "v2", version: 2 }, 201),
    });
    expect(await screen.findByText("Approved, not yet published")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Publish as a new version (1 approved)" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/publish-drafted"))).toBe(true);
    });
  });

  it("can't publish until something is approved", async () => {
    panel([draft("d1", 1, "pending")]);
    const publish = await screen.findByRole("button", {
      name: "Publish as a new version (0 approved)",
    });
    expect((publish as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("ac8 states", () => {
  it("shows nothing to roles that can't draft on templates", async () => {
    panel(() => json({ detail: "forbidden" }, 403));
    await waitFor(() => {
      expect(screen.queryByText("Guidance drafts")).toBeNull();
      expect(screen.queryByText("Couldn't load drafts")).toBeNull();
    });
  });

  it("shows an error when drafts can't load", async () => {
    panel(() => json({ detail: "boom" }, 500));
    expect(await screen.findByText("Couldn't load drafts")).toBeTruthy();
  });

  it("shows the empty state", async () => {
    panel([]);
    expect(await screen.findByText("No drafts to review.")).toBeTruthy();
  });
});
