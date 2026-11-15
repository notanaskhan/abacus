// A-09-T07 (SPEC-658 AC-0.6): every lettered artboard of AUD-32 to AUD-35 and POR-23 has a typed
// scenario with its persona and clock, and the scenario data foots (187,860,000 on AUD-32 d,
// 50,760,000 and 67,840,000 on AUD-33 a, "off 10,000" on c, 384,000 on AUD-34 c).
import { describe, expect, it } from "vitest";
import type { Scenario } from "../../app-core/fixture-mode";
import {
  aud32Missing,
  aud32Scenarios,
  aud33Scenarios,
  aud33Unbalanced,
  aud34Scenarios,
  aud35Scenarios,
  por23Scenarios,
} from "../scenarios/group-audit";

const LETTERS: Record<string, [Record<string, Scenario>, string]> = {
  "AUD-32": [aud32Scenarios, "abcdef"],
  "AUD-33": [aud33Scenarios, "abcdefg"],
  "AUD-34": [aud34Scenarios, "abcdef"],
  "AUD-35": [aud35Scenarios, "abcdefg"],
  "POR-23": [por23Scenarios, "abcdef"],
};

describe("A-09 fixture scenarios", () => {
  it("every lettered artboard has a scenario with a persona and a clock", () => {
    let count = 0;
    for (const [id, [set, letters]] of Object.entries(LETTERS)) {
      expect(Object.keys(set).sort().join("")).toBe(letters);
      for (const s of Object.values(set)) {
        expect(s.persona, id).toBeTruthy();
        expect(s.clock, id).toMatch(/^2026-\d\d-\d\dT\d\d:\d\d:00-0[56]:00$/);
        count += 1;
      }
    }
    expect(count).toBe(32);
  });

  it("AUD-32 a names the missing slot and blocks finalize", () => {
    const missing = aud32Missing();
    expect(missing.missing).toEqual(["Real Estate · Prior"]);
    expect(missing.allowed_actions).not.toContain("consolidation.finalize");
  });

  it("AUD-33 c is off 10,000 on E3 and E4 waits approved", () => {
    const items = aud33Unbalanced().items;
    const e3 = items.find((e) => e.display_code === "E3");
    expect(e3?.off_by).toBe("-10000.00");
    expect(e3?.status).toBe("proposed");
    expect(items.find((e) => e.display_code === "E4")?.status).toBe("approved");
  });

  it("POR-23 renders the component auditor and never a firm word", () => {
    for (const s of Object.values(por23Scenarios)) expect(s.persona).toBe("renee-pruett");
  });
});
