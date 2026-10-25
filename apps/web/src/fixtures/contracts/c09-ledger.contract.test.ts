// A-02-T03 (TASK-1186; SPEC-333 AC-29): the C9 v1 view-by-layer fixture for AUD-06
// (docs/contracts/c09-ledger.md). Typed with the generated client, so a breaking change fails
// `tsc`, and checked against the OpenAPI document at run time. Northwind's E0 figures (blueprint
// §9.4): net assets 16,812,400.00 EOY and 14,228,500.00 BOY; the six funds 14,895,000.00 and
// 12,683,000.00; investments 16,500,000.00 and 13,940,000.00; debits = credits 17,663,450.00.
// Brightwater Hale, synthetic. The pytest half is backend/tests/contracts/c09_ledger/.
import type {
  TbLayerViewOut,
  TrialBalanceLabelStatus,
  TrialBalanceLayerStatus,
} from "@abacus/api-client";
import { type EnumCovered, STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { validateResponse } from "../schema-check";
import { stableId } from "../seed/prng";
import { cents, money, northwindTbView } from "../seed/trial-balance";

/** Every key of T and of every object type nested in it. */
type DeepKeys<T> = T extends readonly (infer U)[]
  ? DeepKeys<U>
  : T extends object
    ? { [K in keyof T & string]: K | DeepKeys<NonNullable<T[K]>> }[keyof T & string]
    : never;
type Hidden = `${string}hidden${string}` | `${string}walled${string}`;
const clean: [Extract<DeepKeys<TbLayerViewOut>, Hidden>] extends [never] ? true : false = true;

// The generated enums are exactly the registry's objects (C2).
const labelsCovered: EnumCovered<"trial_balance_label", TrialBalanceLabelStatus> = true;
const layersCovered: EnumCovered<"trial_balance_layer", TrialBalanceLayerStatus> = true;

const VIEW = "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/layers/{layer}";
const view = northwindTbView(stableId("engagement:northwind:2025"));
const total = (key: string) => {
  const found = view.totals.find((t) => t.key === key);
  if (found === undefined) throw new Error(`no total ${key}`);
  return found;
};

describe("C9 v1 contract (A-02-T03): types", () => {
  it("covers the registry and carries no hidden count", () => {
    expect([clean, labelsCovered, layersCovered]).toEqual([true, true, true]);
    expect(Object.keys(STATUS_REGISTRY)).toEqual(
      expect.arrayContaining(["trial_balance_label", "trial_balance_layer", "tie_out_tally"]),
    );
  });

  it("matches the OpenAPI document", () => {
    expect(validateResponse("get", VIEW, view)).toEqual([]);
  });
});

describe("C9 v1 contract (A-02-T03): Northwind at E0 foots", () => {
  it("foots net assets to 16,812,400.00 EOY and 14,228,500.00 BOY", () => {
    expect(total("net_assets")).toMatchObject({ eoy: "16812400.00", boy: "14228500.00" });
    expect(total("investments")).toMatchObject({ eoy: "16500000.00", boy: "13940000.00" });
    expect(total("mutual_funds")).toMatchObject({ eoy: "14895000.00", boy: "12683000.00" });
  });

  it("balances debits and credits at 17,663,450.00", () => {
    expect(view.balance).toEqual({
      layer: "unadjusted",
      debit: "17663450.00",
      credit: "17663450.00",
      difference: "0.00",
      balanced: true,
    });
  });

  it("re-foots every group's lines to its subtotal", () => {
    for (const group of view.groups) {
      const eoy = group.lines.reduce((a, l) => a + cents(l.eoy), 0n);
      expect(money(eoy), group.key).toBe(group.eoy);
    }
    const lines = view.groups.flatMap((g) => g.lines);
    expect(lines).toHaveLength(15);
    expect(lines.reduce((a, l) => a + cents(l.eoy), 0n)).toBe(0n);
  });

  it("lights KRS Target 2045 at 2,915,330.00 against 2,388,970.00", () => {
    const line = view.groups.flatMap((g) => g.lines).find((l) => l.account_code === "1130");
    expect(line).toMatchObject({ eoy: "2915330.00", boy: "2388970.00", area: "Investments" });
  });

  it("never shows initials on an agent's tick and cites every agreement", () => {
    for (const tick of view.groups.flatMap((g) => g.lines).flatMap((l) => l.ticks ?? [])) {
      if (tick.actor_kind === "agent") expect(tick.initials).toBeNull();
      if (tick.kind === "agreed") expect(tick.citation_id).not.toBeNull();
    }
  });

  it("offers no adjusted layer before an adjustment source is registered", () => {
    expect(view.layers_available).toEqual(["unadjusted"]);
    expect(view.groups.flatMap((g) => g.lines).every((l) => l.final === null)).toBe(true);
  });
});
