import type { EvidenceVersionOut, RequestItemOut, ScreeningResultOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { awaitingScreening, boardRows, confidencePercent, sourceLabel, statusLabel } from "./join";

function item(id: string, versionId?: string | null): RequestItemOut {
  return {
    id,
    engagement_id: "e1",
    description: `Item ${id}`,
    audit_area: "Cash",
    status: "open",
    created_at: "2025-01-01T00:00:00Z",
    ...(versionId === undefined ? {} : { evidence_version_id: versionId }),
  };
}

function version(
  id: string,
  method: EvidenceVersionOut["method"] = "retrieved",
): EvidenceVersionOut {
  return {
    id,
    evidence_item_id: `i-${id}`,
    version_no: 1,
    method,
    source: "fake",
    pulled_at: null,
    period_start: null,
    period_end: null,
    created_at: "2025-01-01T00:00:00Z",
  };
}

function result(versionId: string): ScreeningResultOut {
  return {
    id: `r-${versionId}`,
    evidence_version_id: versionId,
    action: "ready_for_review",
    confidence: "0.900",
    rationale: "ok",
    citations: [],
    unverified: [],
    created_at: "2025-01-01T00:00:00Z",
  };
}

describe("ac18 board join", () => {
  it("gives none for an item without evidence (absent or null version)", () => {
    const rows = boardRows([item("a"), item("b", null)], [], []);
    expect(rows.map((r) => r.screening.kind)).toEqual(["none", "none"]);
    expect(rows.map((r) => r.evidence)).toEqual([null, null]);
  });

  it("gives pending when evidence has no screening result yet", () => {
    const [row] = boardRows([item("a", "v1")], [version("v1")], []);
    expect(row?.screening.kind).toBe("pending");
    expect(row?.evidence?.id).toBe("v1");
  });

  it("gives the result joined on evidence_version_id", () => {
    const rows = boardRows(
      [item("a", "v1"), item("b", "v2")],
      [version("v1"), version("v2")],
      [result("v2")],
    );
    expect(rows[0]?.screening.kind).toBe("pending");
    const second = rows[1]?.screening;
    expect(second?.kind).toBe("result");
    expect(second?.kind === "result" ? second.result.id : null).toBe("r-v2");
  });

  it("keeps the item order and ignores results for other evidence", () => {
    const rows = boardRows([item("b"), item("a", "v1")], [version("v1")], [result("other")]);
    expect(rows.map((r) => r.item.id)).toEqual(["b", "a"]);
    expect(rows[1]?.screening.kind).toBe("pending");
  });

  it("is awaiting screening only while some row is pending", () => {
    const none = boardRows([item("a")], [], []);
    const pending = boardRows(
      [item("a", "v1"), item("b", "v2")],
      [version("v1"), version("v2")],
      [result("v2")],
    );
    const done = boardRows([item("a", "v1")], [version("v1")], [result("v1")]);
    expect(awaitingScreening([])).toBe(false);
    expect(awaitingScreening(none)).toBe(false);
    expect(awaitingScreening(pending)).toBe(true);
    expect(awaitingScreening(done)).toBe(false);
  });

  it("labels the source", () => {
    expect(sourceLabel(version("v", "retrieved"))).toBe("Retrieved");
    expect(sourceLabel(version("v", "uploaded"))).toBe("Uploaded");
  });

  it("labels all four statuses", () => {
    expect(statusLabel("open")).toBe("Open");
    expect(statusLabel("received")).toBe("Received");
    expect(statusLabel("ready_for_review")).toBe("Ready for review");
    expect(statusLabel("needs_revision")).toBe("Needs revision");
  });

  it("shows confidence as a percentage", () => {
    expect(confidencePercent("0.900")).toBe("90%");
    expect(confidencePercent("1")).toBe("100%");
    expect(confidencePercent("0.5")).toBe("50%");
  });
});
