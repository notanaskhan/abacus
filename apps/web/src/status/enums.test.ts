// F-05-T12 AC-3: an OpenAPI enum literal without a registry entry fails `tsc`. The two
// `@ts-expect-error` lines below are the proof: tsc fails this file if either error goes away.
import type { EngagementStatus } from "@abacus/api-client";
import type { EnumCovered } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { OPENAPI_STATUS_ENUMS } from "./enums";

describe("ac3 the OpenAPI status enums and the registry", () => {
  it("covers every enum the generated client holds, both ways", () => {
    expect(OPENAPI_STATUS_ENUMS).toEqual({ engagement: true, request: true, audit_section: true });
  });

  it("fails tsc for a literal with no entry, and for a stored code the enum lacks", () => {
    // @ts-expect-error "mystery" has no entry under engagement in status-vocabulary.yaml
    const missingFromRegistry: EnumCovered<"engagement", EngagementStatus | "mystery"> = true;
    // @ts-expect-error "archived" is a stored engagement code the enum no longer carries
    const missingFromEnum: EnumCovered<"engagement", Exclude<EngagementStatus, "archived">> = true;
    expect([missingFromRegistry, missingFromEnum]).toEqual([true, true]);
  });

  it("never counts a derived code as missing from an enum", () => {
    const requestWithoutOverdue: EnumCovered<
      "request",
      "draft" | "requested" | "uploaded" | "received" | "returned" | "not_applicable"
    > = true;
    expect(requestWithoutOverdue).toBe(true);
  });
});
