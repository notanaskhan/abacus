import { describe, expect, it } from "vitest";
import { CONNECTED_AS_YOU, type FlowEvent, type FlowState, needsStepUp, next } from "./flow";

// W-01-T17: Hannah connects Google Workspace through the fake provider and sees Connected as
// you; a stale session steps up MFA before acting; a failed callback can be retried.

function run(events: FlowEvent[], stale = false): FlowState {
  return events.reduce<FlowState>((s, e) => next(s, e, stale), "idle");
}

describe("the Connect flow", () => {
  it("connects through consent and the provider's callback", () => {
    const end = run([
      { type: "enable" },
      { type: "confirm" },
      { type: "continue" },
      { type: "callback", ok: true },
      { type: "settled" },
    ]);
    expect(end).toBe("connected");
    expect(CONNECTED_AS_YOU).toBe("✓ Connected as you");
  });

  it("steps up MFA before acting on a stale session", () => {
    expect(next("idle", { type: "enable" }, true)).toBe("step_up");
    expect(next("idle", { type: "reconnect" }, true)).toBe("step_up");
    expect(next("step_up", { type: "confirm" }, true)).toBe("step_up");
    expect(next("step_up", { type: "mfa_done" }, true)).toBe("confirm");
    const now = new Date("2026-09-14T14:24:00Z");
    expect(needsStepUp(new Date("2026-09-14T14:00:00Z"), now)).toBe(true);
    expect(needsStepUp(new Date("2026-09-14T14:20:00Z"), now)).toBe(false);
    expect(needsStepUp(null, now)).toBe(true);
  });

  it("ends a refused callback in an error the person retries from consent", () => {
    const failed = run([
      { type: "reconnect" },
      { type: "continue" },
      { type: "callback", ok: false },
    ]);
    expect(failed).toBe("error");
    expect(next(failed, { type: "retry" }, false)).toBe("consent");
    expect(next("consent", { type: "cancel" }, false)).toBe("idle");
  });
});
