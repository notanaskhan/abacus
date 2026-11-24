// T-06-T45 (DEC-5937): the shared banner's sentence (TXP-13 d, TXP-02 DF-08) is the landing's:
// an audit's Final TB, a close's locked TB, and nothing without a hand-off.
import { describe, expect, it } from "vitest";
import { handoffLine } from "./HandoffProvenanceBanner";

const NOW = new Date("2026-11-09T17:00:00Z");

describe("handoffLine", () => {
  it("reads exactly as the TXP-13 revision for an audit hand-off", () => {
    expect(
      handoffLine(
        {
          handoff_id: "00000000-0000-4000-8000-000000000001",
          source_kind: "audit_release",
          source_label: "FY2026 audit",
          handed_off_at: "2026-11-09T16:30:00Z",
        },
        NOW,
      ),
    ).toBe("From FY2026 audit · Final TB · handed off Nov 9");
  });

  it("names a close's locked TB for a close_lock hand-off", () => {
    expect(
      handoffLine(
        {
          handoff_id: "00000000-0000-4000-8000-000000000002",
          source_kind: "close_lock",
          source_label: "FY2026 December close",
          handed_off_at: "2027-01-12T20:15:00Z",
        },
        NOW,
      ),
    ).toBe("From FY2026 December close · locked close TB · handed off Jan 12, 2027");
  });

  it("is null for a return with no hand-off", () => {
    expect(handoffLine({}, NOW)).toBeNull();
  });
});
