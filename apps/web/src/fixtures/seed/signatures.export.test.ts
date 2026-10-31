// N-02-T36 (DEC-1573): the SIG-01 hub fixtures are the Python scenario's. `make fixtures` writes
// `scenario.signatures-hub.json` from the `signatures` slice (no database); this holds the
// TypeScript scenarios (N-02-T10's `signatures.ts`) to it row for row, with the hub's counts.
import { describe, expect, it } from "vitest";
import exported from "./scenario.signatures-hub.json";
import {
  COMPLETED,
  DUE_WITHIN_7,
  EXPIRED,
  HUB_COUNTS,
  type HubEnvelope,
  OUT,
  TO_SEND,
} from "./signatures";

const shape = (e: HubEnvelope) => ({
  key: e.key,
  title: e.title,
  client: e.client,
  purpose: e.purpose,
  signers: e.signers.map((s) => ({ name: s.name, signed: s.signed })),
  sent: e.sent,
  viewed: e.viewed,
  due: e.due,
  workItem: e.workItem,
  status: e.status,
  ...(e.outcome === undefined ? {} : { outcome: e.outcome }),
});

describe("SIG-01 fixtures match the Python scenario at E0", () => {
  it("out for signature, to send, completed and expired, row for row", () => {
    expect(OUT.map(shape)).toEqual(exported.out);
    expect(TO_SEND.map(shape)).toEqual(exported.toSend);
    expect(COMPLETED.map(shape)).toEqual(exported.completed);
    expect(EXPIRED.map(shape)).toEqual(exported.expired);
  });

  it("the tab counts, tiles and by-type tile", () => {
    expect(exported.counts).toEqual(HUB_COUNTS);
    const soon = exported.out
      .filter((e) => e.due !== null && e.due >= "2026-09-14" && e.due <= "2026-09-21")
      .map((e) => e.key);
    expect(soon).toEqual([...DUE_WITHIN_7]);
  });
});
