// HOME-02's ?ov= deep links (P-04-T52, I-01): a decision row opens SHL-11 and a sign-off row
// SHL-12 as a layer over the queue; any other row opens its host.
import type { HumanGateOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { encodeRef } from "../../app-core/overlays";
import { openOverlayOf } from "./hosts";

const gate = (over: Partial<HumanGateOut>): HumanGateOut =>
  ({
    id: "g1",
    kind: "decision",
    subject: { type: "decision_card", id: "card-1" },
    ...over,
  }) as HumanGateOut;

const link = (g: HumanGateOut): string | undefined => {
  const ref = openOverlayOf(g);
  return ref === undefined ? undefined : encodeRef(ref);
};

describe("openOverlayOf", () => {
  it("a decision card row opens ?ov=decision:<cardId>", () => {
    expect(link(gate({}))).toBe("decision:card-1");
  });

  it("a sign-off row opens ?ov=signoff:<type>:<id>", () => {
    const row = gate({
      kind: "sign_off_request",
      subject: { type: "return_section", id: "sec-9" },
    });
    expect(link(row)).toBe("signoff:return_section:sec-9");
  });

  it("the owner's overlay code wins over the kind", () => {
    const row = gate({
      kind: "proposal",
      overlay: "sign_off",
      subject: { type: "aje", id: "A:1" },
    });
    expect(link(row)).toBe("signoff:aje:A%3A1");
  });

  it("an acceptance decision or a send opens its host instead", () => {
    expect(link(gate({ subject: { type: "acceptance_decision_due", id: "x" } }))).toBeUndefined();
    expect(link(gate({ kind: "send", subject: { type: "letter", id: "y" } }))).toBeUndefined();
  });
});
