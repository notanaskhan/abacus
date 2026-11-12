// T-05-T28 (TASK-7520; T-05 F1): "A 1065 opens on Agent while a 1040 still opens TAX-02, and every
// Group B slug outside the form redirects to the default tab."
import { describe, expect, it } from "vitest";
import {
  GROUP_A,
  GROUP_B,
  P1_REVIEW,
  SCREEN_OF,
  TAB_LABEL,
  isEntityForm,
  sectionOf,
  slugOf,
} from "./entityReturn";

describe("entity return sections", () => {
  it("dispatches a 1065 to the entity layout and keeps 1040 and 1041 on TAX-02", () => {
    expect(isEntityForm("1065")).toBe(true);
    for (const form of ["1040", "1041", "1120s", null, undefined]) {
      expect(isEntityForm(form)).toBe(false);
    }
  });

  it("opens on Agent and reads Group A in the reviewer's order", () => {
    expect(sectionOf(undefined)).toEqual({ tab: "agent" });
    expect(GROUP_A.map((t) => TAB_LABEL[t])).toEqual([
      "Agent",
      "Issues",
      "Workpaper",
      "Review",
      "Intake",
      "Activity",
    ]);
    expect(SCREEN_OF.agent).toBe("TXP-00");
  });

  it("validates Review's Group B slugs and refuses anything else", () => {
    expect(sectionOf("review", "schedule-k")).toEqual({ tab: "review", review: "schedule-k" });
    expect(sectionOf("review")).toEqual({ tab: "review", review: "summary" });
    for (const bad of ["provision", "SCHEDULE-K", "../agent"]) {
      expect(sectionOf("review", bad)).toBeNull();
    }
    expect(sectionOf("payroll")).toBeNull();
    expect(sectionOf("issues", "extra")).toBeNull();
  });

  it("names the four P1 review tabs as planned", () => {
    expect([...P1_REVIEW].sort()).toEqual(["basis", "fixed-assets", "m1-m3", "states"]);
    expect(GROUP_B).toHaveLength(9);
  });

  it("round-trips sections to paths", () => {
    expect(slugOf({ tab: "agent" })).toBe("");
    expect(slugOf({ tab: "workpaper" })).toBe("/workpaper");
    expect(slugOf({ tab: "review", review: "capital" })).toBe("/review/capital");
  });
});
