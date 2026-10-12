// SPEC-029 AC-12, AC-13 (TASK-056): the viewer shows server-made pages and extracted values,
// plain text only, with loading, pending, none, error and not-allowed states.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, never, renderRoutes, signInForTest } from "../testing/support";
import { EvidencePreview, type PreviewSource } from "./EvidencePreview";

const E = "e1";
const SOURCE: PreviewSource = { kind: "upload", engagementId: E, itemId: "i1", versionId: "v1" };
const BASE = `/v1/engagements/${E}/request-items/i1/uploads/v1/preview`;

const view = (source: PreviewSource = SOURCE): void => {
  renderRoutes([{ path: "/", component: () => <EvidencePreview source={source} /> }]);
};

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
  vi.stubGlobal(
    "URL",
    Object.assign(URL, { createObjectURL: () => "blob:page", revokeObjectURL: () => undefined }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const png = (): Response =>
  new Response(new Uint8Array([0x89, 0x50, 0x4e, 0x47]), {
    headers: { "Content-Type": "image/png" },
  });

describe("ac12 pages", () => {
  it("shows page images from the server and moves between pages", async () => {
    const { calls } = mockApi({
      [`GET ${BASE}`]: () =>
        json({ kind: "pages", reason: null, page_count: 2, truncated: false, sheets: [] }),
      [`GET ${BASE}/pages/1`]: () => png(),
      [`GET ${BASE}/pages/2`]: () => png(),
    });
    view();
    expect(await screen.findByAltText("Page 1")).toBeTruthy();
    expect(screen.getByText("Page 1 of 2")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByAltText("Page 2")).toBeTruthy();
    expect(calls.some((c) => c.path.endsWith("/pages/2"))).toBe(true);
  });

  it("says when only the first pages are shown", async () => {
    mockApi({
      [`GET ${BASE}`]: () =>
        json({ kind: "pages", reason: null, page_count: 1, truncated: true, sheets: [] }),
      [`GET ${BASE}/pages/1`]: () => png(),
    });
    view();
    expect(await screen.findByText(/first pages only/)).toBeTruthy();
  });
});

describe("ac12 tables", () => {
  it("shows a spreadsheet's values as plain text, formulas included as typed", async () => {
    mockApi({
      [`GET ${BASE}`]: () =>
        json({
          kind: "table",
          reason: null,
          page_count: 0,
          truncated: false,
          sheets: [
            {
              name: "AR Aging",
              rows: [
                ["Customer", "Total"],
                ["Acme", "175.00"],
                ['=HYPERLINK("x")', "@SUM"],
              ],
            },
            { name: "Notes", rows: [["Note"], ["Hello"]] },
          ],
        }),
    });
    view();
    expect(await screen.findByRole("table", { name: "Spreadsheet preview" })).toBeTruthy();
    expect(screen.getByText('=HYPERLINK("x")')).toBeTruthy();
    expect(screen.getByText("@SUM")).toBeTruthy();
    expect(document.querySelector("a")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Notes" }));
    expect(await screen.findByText("Hello")).toBeTruthy();
  });
});

describe("ac13 states", () => {
  it("shows a loading state", async () => {
    mockApi({ [`GET ${BASE}`]: () => never() });
    view();
    await waitFor(() => {
      expect(document.querySelector(".animate-pulse")).not.toBeNull();
    });
  });

  it("says the preview is being prepared while the workflow runs", async () => {
    mockApi({
      [`GET ${BASE}`]: () =>
        json({ kind: "pending", reason: null, page_count: 0, truncated: false, sheets: [] }),
    });
    view();
    expect(await screen.findByText("Preparing the preview…")).toBeTruthy();
  });

  it("explains why there is no preview", async () => {
    mockApi({
      [`GET ${BASE}`]: () =>
        json({ kind: "none", reason: "encrypted", page_count: 0, truncated: false, sheets: [] }),
    });
    view();
    expect(await screen.findByText(/password-protected/)).toBeTruthy();
  });

  it("shows an error, and a not-allowed state", async () => {
    mockApi({ [`GET ${BASE}`]: () => json({ detail: "x" }, 500) });
    view();
    expect(await screen.findByText("Couldn't load the preview")).toBeTruthy();
    cleanup();
    mockApi({ [`GET ${BASE}`]: () => json({ detail: "forbidden" }, 403) });
    view();
    expect(await screen.findByText("You can't preview this file.")).toBeTruthy();
  });

  it("previews an inbox file through the inbox's route", async () => {
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}/inbox/f1/preview`]: () =>
        json({
          kind: "none",
          reason: "not_previewable",
          page_count: 0,
          truncated: false,
          sheets: [],
        }),
    });
    view({ kind: "inbox", engagementId: E, fileId: "f1" });
    expect(await screen.findByText(/Preview isn't available/)).toBeTruthy();
    expect(calls.some((c) => c.path.endsWith("/inbox/f1/preview"))).toBe(true);
  });
});
