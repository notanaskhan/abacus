// T-05-T66 (SPEC-651 AC-13.1): a refused capability is never offered and always has words.
import { describe, expect, it } from "vitest";
import { ENTITY_CAPABILITIES, entityAgentGate } from "./agents";

const memo = ENTITY_CAPABILITIES.memo;

describe("entityAgentGate", () => {
  it("offers nothing while the capabilities load (fail closed)", () => {
    expect(entityAgentGate(undefined, memo)).toEqual({
      offered: false,
      reason: null,
      consent: false,
    });
  });

  it("offers an available capability", () => {
    const gate = entityAgentGate({ items: [{ capability: memo, available: true }] }, memo);
    expect(gate.offered).toBe(true);
    expect(gate.reason).toBeNull();
  });

  it("names the reason when agents are off", () => {
    const gate = entityAgentGate(
      { items: [{ capability: memo, available: false, reason: "agent" }] },
      memo,
    );
    expect(gate.offered).toBe(false);
    expect(gate.reason).toMatch(/Prepare this by hand/u);
  });

  it("marks a §7216 refusal as consent", () => {
    const gate = entityAgentGate(
      { items: [{ capability: memo, available: false, reason: "consent_7216" }] },
      memo,
    );
    expect(gate.consent).toBe(true);
    expect(gate.reason).toMatch(/§7216/u);
  });

  it("refuses a capability the server did not list", () => {
    const gate = entityAgentGate({ items: [] }, memo);
    expect(gate.offered).toBe(false);
    expect(gate.reason).not.toBeNull();
  });
});
