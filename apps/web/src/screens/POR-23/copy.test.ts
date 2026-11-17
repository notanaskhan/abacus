import { describe, expect, it } from "vitest";
import { COPY } from "./copy";

describe("POR-23 words (A-09-T32)", () => {
  it("reads the handoff's intro and progress", () => {
    expect(COPY.component("Harlow & Pike Distribution, Inc.")).toBe(
      "Component: Harlow & Pike Distribution, Inc.",
    );
    expect(COPY.progress(0, 4)).toBe("0 of 4 deliverables");
    expect(COPY.deliverables(2, 4)).toBe("Deliverables · 2 of 4");
  });

  it("uses client words only, never the firm's", () => {
    const words = JSON.stringify(COPY);
    for (const banned of ["Accrued", "Expected", "Reviewed", "Late", "Received", "via Agent"]) {
      expect(words).not.toContain(banned);
    }
    expect(COPY.word.due("Oct 2")).toBe("Due Oct 2");
    expect(COPY.word.you_uploaded("Oct 1")).toBe("✓ You uploaded Oct 1");
  });
});
