// DEC-1273: the designed links wired for TAX-01, TAX-02, HOME-02, SHL-16 and ADM-05 resolve
// through the manifest's builders: hrefs for routed screens, `ov.<ID>()` for overlay screens.
import type { HumanGateOut, LinkOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { linkedHref } from "../screens/FIL-01";
import { MY_WORK, openHref } from "../screens/HOME-02/hosts";
import { hrefOf, ov, to } from "./to";

const ID = "6b1f2a40-6f0e-4a8c-9a39-0b0f3c8e2f11";

function gate(subject_route: string | null): HumanGateOut {
  return { subject_route } as unknown as HumanGateOut;
}

describe("hrefOf", () => {
  it("fills the path's params and appends the search", () => {
    expect(hrefOf(to.TAX02({ returnId: ID }))).toBe(`/tax-returns/${ID}`);
    expect(hrefOf(to.TAX01(), { tile: "action_required" })).toBe(
      "/tax-returns?tile=action_required",
    );
    expect(hrefOf(to.CLI05({ clientId: ID, sub: "consents" }))).toBe(
      `/clients/${ID}/tax-profile/consents`,
    );
  });
});

describe("ov builders", () => {
  it("SHL-16 opens the checkpoint drawer over its target", () => {
    expect(ov.SHL16("tax_return", ID)).toEqual({ key: "checkpoints", args: ["tax_return", ID] });
  });
});

describe("HOME-02's hosts", () => {
  it("opens a return's final approval on TAX-02 and the other hosts as HOME-01 does", () => {
    expect(openHref(gate(`TAX-02?returnId=${ID}`))).toBe(`/tax-returns/${ID}`);
    expect(openHref(gate(`BND-02?binderId=${ID}&request=${ID}`))).toBe(
      `/binders/${ID}?request=${ID}`,
    );
  });

  it("opens nothing for a path, an unrouted screen or an id that is not a UUID", () => {
    expect(openHref(gate("/tax-returns"))).toBeUndefined();
    expect(openHref(gate("//evil.example/x"))).toBeUndefined();
    expect(openHref(gate(`TAX-03?returnId=${ID}`))).toBeUndefined();
    expect(openHref(gate("TAX-02?returnId=feld"))).toBeUndefined();
    expect(openHref(gate(null))).toBeUndefined();
  });

  it("My work is HOME-01", () => {
    expect(MY_WORK).toBe("/home");
  });
});

describe("FIL-01's Linked to", () => {
  const link = (kind: LinkOut["kind"], route: string): LinkOut => ({ kind, label: "x", route });

  it("a return line opens TAX-02 for its return; anything else stays text", () => {
    expect(linkedHref(link("return_line", `/tax-returns/${ID}`))).toBe(`/tax-returns/${ID}`);
    expect(linkedHref(link("return_line", "/tax-returns"))).toBeUndefined();
    expect(linkedHref(link("request", `/requests/items/${ID}`))).toBeUndefined();
  });
});
