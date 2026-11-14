// W-02-T22 (TASK-7947; DF-04; W-02 §3.9): "Each state renders words and a disabled composer with
// its reason and never offers a control the server would refuse."
import { describe, expect, it } from "vitest";
import { COPY } from "./copy";
import { availabilityOf } from "./Thread";

const caps = (available: boolean, reason?: string) => ({
  items: [{ capability: "workbench.assistant", available, reason: reason ?? null }],
});

describe("WB-01 unavailable and gated states", () => {
  it("available: no reason, the composer is on", () => {
    expect(availabilityOf(caps(true))).toEqual({ reason: null, consent: false });
  });

  it.each([
    ["ai_excluded", COPY.unavailable, false],
    ["ai_policy_off", COPY.unavailable, false],
    ["paused", COPY.paused, false],
    ["consent_7216", COPY.consentOff, true],
    ["not_on_team", COPY.notOnTeam, false],
  ])("%s: the words, and Request consent only for consent", (code, words, consent) => {
    expect(availabilityOf(caps(false, code))).toEqual({ reason: words, consent });
  });

  it("an unknown or missing capability fails closed", () => {
    expect(availabilityOf({ items: [] }).reason).toBe(COPY.unavailable);
    expect(availabilityOf(caps(false, "something_new")).reason).toBe(COPY.unavailable);
  });

  it("before the read lands, nothing is claimed either way", () => {
    expect(availabilityOf(undefined)).toEqual({ reason: null, consent: false });
  });
});
