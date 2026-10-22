// TASK-334: values point back to where they were printed: a snippet on hover, the viewer on
// click, the line outlined.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { findLine } from "./EvidencePreview";
import { cropStyle, SourceHover } from "./SourceHover";
import { pageOf } from "./Workpaper";

const PREVIEW = "/v1/engagements/e1/evidence-versions/v1/preview";
const SHEET = {
  kind: "table",
  reason: null,
  page_count: 0,
  truncated: false,
  sheets: [
    {
      name: "TB",
      rows: [
        ["Code", "Account", "Debit"],
        ["1000", "Cash", "161345.67"],
      ],
    },
  ],
  page_lines: [],
};

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("TASK-334 source pointers", () => {
  it("finds a quoted line and crops around a box (pure)", () => {
    const lines = [
      {
        text: "Previous Balance $1,250.00",
        box: [0.08, 0.1, 0.29, 0.11] as [number, number, number, number],
      },
      {
        text: "New  Balance $1,209.58",
        box: [0.08, 0.15, 0.26, 0.16] as [number, number, number, number],
      },
    ];
    expect(findLine(lines, "new balance")).toEqual([0.08, 0.15, 0.26, 0.16]);
    expect(findLine(lines, "missing")).toBeNull();
    const crop = cropStyle([0.08, 0.15, 0.26, 0.16], 792 / 612);
    expect(crop.width).toBeCloseTo(748);
    expect(crop.left).toBe(0); // a line near the left edge doesn't scroll past the page edge
    expect(crop.top).toBeLessThan(0); // scrolled down to the line
    expect(pageOf("Harborline report, page 2, line 7")).toBe(2);
    expect(pageOf("p. 14")).toBe(14);
    expect(pageOf("cell C9")).toBeUndefined();
  });

  it("hovering a value shows its cell among its neighbours; clicking opens the viewer", async () => {
    mockApi({ [`GET ${PREVIEW}`]: () => json(SHEET) });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <SourceHover
            engagementId="e1"
            source={{ versionId: "v1", cell: "C2" }}
            label="the debit"
          >
            161,345.67
          </SourceHover>
        ),
      },
    ]);
    const trigger = await screen.findByRole("button", {
      name: "the debit: show where it came from (cell C2)",
    });
    fireEvent.mouseEnter(trigger);
    expect(await screen.findByText("From cell C2 · click to open")).toBeTruthy();
    expect((await screen.findAllByText("161345.67")).length).toBeGreaterThan(0);
    fireEvent.click(trigger);
    await waitFor(() => {
      expect(screen.getByText("The cited cell, C2, is highlighted.")).toBeTruthy();
    });
  });

  it("a PDF value without a box says which page it is on", async () => {
    mockApi({
      [`GET ${PREVIEW}`]: () =>
        json({
          kind: "pages",
          reason: null,
          page_count: 2,
          truncated: false,
          sheets: [],
          page_lines: [],
        }),
    });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <SourceHover engagementId="e1" source={{ versionId: "v1", page: 2 }} label="the memo">
            PI-02 memo
          </SourceHover>
        ),
      },
    ]);
    fireEvent.focus(await screen.findByRole("button", { name: /the memo/ }));
    expect(await screen.findByText("Page 2. Click to open the document.")).toBeTruthy();
  });
});
