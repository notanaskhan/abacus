// F-03-T09 (C2): the generated registry drives words and tones; portal wording and placeholders.
import { registryWord, STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";

describe("C2 status registry", () => {
  it("reads labels and tones from the generated data", () => {
    expect(registryWord("request", "received")).toEqual({ label: "Received ✓", tone: "success" });
    expect(registryWord("request", "uploaded").label).toBe("Uploaded – needs review");
    expect(registryWord("engagement", "contracted").label).toBe("Letter signed");
  });

  it("uses the client wording in the portal and fills placeholders", () => {
    expect(registryWord("request", "not_applicable", { client: true }).label).toBe("Ignored");
    expect(registryWord("request", "returned", { fill: { reason: "wrong year" } }).label).toBe(
      "Returned · wrong year",
    );
    expect(registryWord("request", "returned").label).toBe("Returned");
  });

  it("never uses the match variant, and an unknown code reads as itself", () => {
    const objects: Record<string, Record<string, { variant: string | null }>> = STATUS_REGISTRY;
    const variants = Object.values(objects).flatMap((codes) =>
      Object.values(codes).map((c) => c.variant),
    );
    expect(variants).not.toContain("match");
    expect(registryWord("request", "mystery")).toEqual({ label: "mystery", tone: "neutral" });
  });
});
