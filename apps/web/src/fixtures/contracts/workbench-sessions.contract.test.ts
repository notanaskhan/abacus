// W-02-T05 (TASK-7606): the workbench-sessions family's consumer assertions for WB-01 a–g,
// WB-02 a–f and WB-03 d/d2 (docs/contracts/workbench-sessions.md). The fixtures are typed with
// the generated client, so a breaking change fails `tsc`, and each is validated against the
// OpenAPI document at run time, so a field an artboard reads cannot be dropped silently. The
// pytest half is backend/tests/contracts/workbench_sessions/.
import { describe, expect, it } from "vitest";
import { validateResponse, validateSchema } from "../schema-check";
import {
  FIRM_WIDE,
  NEW_SESSION,
  actionRequiredDrill,
  artifactPreview,
  attachedContext,
  contextOptions,
  wbList,
  type WbListScenario,
} from "../seed/workbench";

const LISTS: Record<string, WbListScenario> = {
  "WB-01 a, b, d": "wb01-list-e0",
  "WB-01 c (9:24)": "wb01c-running-three",
  "WB-01 c (9:25)": "wb01c-running-four",
  "WB-01 e": "wb01e-request-chaser-failed",
  "WB-01 f": "wb01f-search-k3",
  "WB-01 g": "wb01g-locked-copperleaf",
};

describe("workbench-sessions consumer (WB-01, WB-02, WB-03)", () => {
  it.each(Object.entries(LISTS))(
    "%s list validates against GET /v1/workbench/sessions",
    (_, s) => {
      expect(validateResponse("get", "/v1/workbench/sessions", wbList(s))).toEqual([]);
    },
  );

  it("the blank session validates against POST /v1/workbench/sessions (WB-02 a)", () => {
    expect(validateSchema("SessionSummaryOut", NEW_SESSION)).toEqual([]); // 201
  });

  it.each(["client_record", "documents", "workpapers"] as const)(
    "the %s picker tab validates (WB-02 b)",
    (tab) => {
      expect(
        validateResponse("get", "/v1/workbench/context-options", contextOptions(tab)),
      ).toEqual([]);
    },
  );

  it("attached and firm-wide context validate (WB-02 a, c, d, f)", () => {
    const path = "/v1/workbench/sessions/{session_id}/context";
    expect(validateSchema("ContextItemsOut", attachedContext())).toEqual([]); // 201
    expect(validateResponse("delete", `${path}/{item_id}`, FIRM_WIDE)).toEqual([]);
  });

  it("the drill and the O4 preview validate (WB-03 d, d2)", () => {
    expect(validateSchema("DrillOut", actionRequiredDrill())).toEqual([]); // 201
    expect(
      validateResponse("get", "/v1/run-artifacts/{artifact_id}/preview", artifactPreview()),
    ).toEqual([]);
  });

  it("a locked row carries metadata only (WB-01 g, INV-3)", () => {
    const locked = wbList("wb01g-locked-copperleaf").items.find((r) => r.locked);
    if (locked === undefined) throw new Error("WB-01 g has a locked row");
    expect([locked.needs_answer, locked.running, locked.ready_for_review]).toEqual([
      false,
      false,
      false,
    ]);
  });
});
