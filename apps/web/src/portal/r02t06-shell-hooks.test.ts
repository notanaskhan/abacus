// R-02-T06 (TASK-6115; R-02 §5.1): the portal's pre-window hooks for POR-08, POR-09 and POR-15.
// Row: "Merged by the Thu Dec 23, 2027 train with production portal output unchanged, while
// fixture builds reach all three routes."
import { describe, expect, it } from "vitest";
import {
  GOVERNANCE_AREAS,
  K1S_SECTION_TARGET,
  governanceNav,
  portalToolbarData,
} from "../domain/portal";
import { AREA_PATHS, PLANNED_AREA_PATHS, portalTree } from "../routes/portal/index";

function paths(): string[] {
  return (portalTree.children as unknown as { path: string }[]).map((route) => route.path);
}

describe("R-02's portal shell hooks", () => {
  it("the three routes and their detail routes exist", () => {
    for (const path of [
      "/approvals",
      "/deliverables",
      "/deliverables/$deliverableId",
      "/governance",
      "/governance/$communicationId",
    ]) {
      expect(paths()).toContain(path);
    }
  });

  it("production's nav map is unchanged; the planned areas are a separate, fixture-only map", () => {
    expect(Object.keys(AREA_PATHS)).toEqual(["Home", "Documents", "Sign", "Questions", "My K-1s"]);
    expect(PLANNED_AREA_PATHS).toEqual({
      Approvals: "/approvals",
      Deliverables: "/deliverables",
      Communications: "/governance",
    });
  });

  it("a tcwg scope draws the room's reduced nav, never management's", () => {
    const bar = portalToolbarData(
      "Victoria Lam",
      {
        nav: ["home", "documents", "approvals", "deliverables"],
        scopes: [
          {
            id: "room-1",
            kind: "governance_room",
            label: "Benefits Committee",
            role_label: "Chair",
          },
        ],
      } as never,
      "room-1",
    );
    expect(bar.nav.map((item) => item.label)).toEqual([
      "Communications",
      "Reports",
      "Questions for you",
    ]);
  });

  it("Questions for you carries its count", () => {
    expect(governanceNav(2).find((item) => item.label === "Questions for you")?.count).toBe(2);
    expect(governanceNav().every((item) => item.count === undefined)).toBe(true);
    expect(GOVERNANCE_AREAS).toHaveLength(3);
  });

  it("T-02's My K-1s banner target is POR-09's K-1 section", () => {
    expect(K1S_SECTION_TARGET).toBe("/deliverables?section=k1s");
  });
});
