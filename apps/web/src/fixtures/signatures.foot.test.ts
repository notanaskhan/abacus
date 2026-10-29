// N-02-T10 (DEC-826): the signatures seed foots. Acceptance (the task row): "Every scenario loads
// in fixture mode and the seed tests foot 8 + 5 + 4 = 17 and 6,500 + 12,000 = 18,500."
import { describe, expect, it } from "vitest";
import { SIG01_SCENARIOS, rowOf, summaryOf } from "./handlers/signatures";
import { DUE_WITHIN_7, E13_FEE, HUB_COUNTS, OUT, TO_SEND } from "./seed/signatures";
import { ENVELOPES } from "./seed/tax/envelopes";

const E0 = "2026-09-14";
const days = (from: string, to: string): number =>
  (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000;

describe("signatures seed", () => {
  it("AC: the out tiles foot 8 + 5 + 4 = 17", () => {
    const count = (status: string): number => OUT.filter((e) => e.status === status).length;
    expect([count("sent"), count("viewed"), count("partially_signed")]).toEqual([
      HUB_COUNTS.tiles.sent,
      HUB_COUNTS.tiles.viewed,
      HUB_COUNTS.tiles.partially_signed,
    ]);
    expect(count("sent") + count("viewed") + count("partially_signed")).toBe(17);
    expect(OUT).toHaveLength(HUB_COUNTS.out);
  });

  it("AC: E13's fee foots 6,500 + 12,000 = 18,500 (BigInt, never the browser's floats)", () => {
    const total = E13_FEE.lines.reduce((sum, line) => sum + BigInt(line.amount), 0n);
    expect(total).toBe(BigInt(E13_FEE.total));
    expect(total).toBe(18_500n);
  });

  it("four are due within seven days of E0: E3, E7, E14, E11", () => {
    const due = OUT.filter((e) => e.due !== null && days(E0, e.due) <= 7).map((e) => e.key);
    expect(due.sort()).toEqual([...DUE_WITHIN_7].sort());
  });

  it("the ten 8879-family rows are F-06-T02's ten envelopes", () => {
    const tax = OUT.filter((e) => e.purpose === "form_8879").map((e) => e.key);
    expect(tax.sort()).toEqual(ENVELOPES.map((e) => e.key).sort());
    expect(HUB_COUNTS.byType.efile).toBe(tax.length);
  });

  it("partial signing reads per-signer chips (E2: ✓ Thomas · ○ Irene)", () => {
    const e2 = OUT.find((e) => e.key === "E2");
    expect(e2 === undefined ? null : rowOf(e2).signer_chips).toEqual([
      { name: "Thomas", signed: true },
      { name: "Irene", signed: false },
    ]);
  });

  it("To send holds two drafts and the agent's needs Grace to send it", () => {
    expect(TO_SEND).toHaveLength(HUB_COUNTS.toSend);
    const agent = TO_SEND.find((e) => e.draftedBy === "Accrued Agent");
    expect(agent === undefined ? null : rowOf(agent).status).toBe("draft");
  });

  it("every SIG-01 scenario loads", () => {
    for (const [state, scenario] of Object.entries(SIG01_SCENARIOS)) {
      expect(scenario.state).toBe(state);
      expect(Object.keys(scenario.handlers)).toContain("GET /v1/envelopes");
    }
    expect(summaryOf({ toSend: [], declined: null }).to_send).toBe(0);
  });
});
