// P-09-T13 (TASK-5008): the trace deep-links as `?ov=run-trace:<runId>`, from any firm route.
import { describe, expect, it } from "vitest";
import { layerOfKey } from "../../app-core/overlays";
import { RUN_TRACE_KEY } from "../../routes/firm/run-trace";
import { RUN_TRACE_OVERLAY, traceLink } from "./links";

describe("WB-09 overlay", () => {
  it("registers the same key the domain links with, as a drawer", () => {
    expect(RUN_TRACE_KEY).toBe(RUN_TRACE_OVERLAY);
    expect(layerOfKey(RUN_TRACE_OVERLAY)).toBe("drawer");
  });

  it("copies this page's link with only the trace open", () => {
    expect(traceLink("r-1", "https://app.example/engagements/e?ov=viewer%3Av&tab=x")).toBe(
      "https://app.example/engagements/e?tab=x&ov=run-trace%3Ar-1",
    );
  });
});
