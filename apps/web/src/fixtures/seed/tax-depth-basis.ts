// T-06-T31 (TASK-8753): Ridgeline's inside and outside basis at 12/31/2025 in fixture mode, as
// `GET /v1/tax-returns/{id}/basis` answers it (TXP-08 a–e). Each partner's inside share is its tax
// capital plus its §752 share, and its outside basis is as the reconciliation shows it, both the
// T-06-T22 slice's (ridgeline_depth_slice.py BASIS). The §752 split (TXP-08 e) is qualified
// nonrecourse 10,712,500 and other nonrecourse 335,800 by year-end profit % (2 · 38 · 30 · 5 · 25,
// seed/tax-entity partners' second period); each partner's two parts equal its §752 share in the
// slice. tax-depth-basis.foot.test.ts re-adds them (ADR-050).
import type { TaxDepthBasisOut, TaxDepthPartnerBasisOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type BasisView = TaxDepthBasisOut["view"];

type P = readonly [
  key: string,
  name: string,
  inside: string,
  outside: string,
  qnr: string,
  other: string,
];

const PARTNERS: readonly P[] = [
  ["gp", "Ridgeline GP LLC", "314090", "314090", "214250", "6716"],
  ["shah", "Meera Shah", "6727710", "6727710", "4070750", "127604"],
  ["psv", "Pell Street Ventures LLC", "5311350", "5311350", "3213750", "100740"],
  ["ps2", "Pell Street II LLC", "885225", "913820", "535625", "16790"],
  ["feld", "Jonah Feld", "4676125", "4676125", "2678125", "83950"],
];

export const PARTNER_ID = (key: string): string => stableId(`partner:ridgeline:${key}`);
export const PELL_II_ID = PARTNER_ID("ps2");
export const FELD_ID = PARTNER_ID("feld");
/** §743(b) placeholder pending §754: 360,000 − 331,405 (TXP-08 note). */
export const PELL_II_PLACEHOLDER = "28595";

function partner([key, name, inside, outside, qnr, other]: P): TaxDepthPartnerBasisOut {
  return {
    partner_id: PARTNER_ID(key),
    name,
    inside,
    outside,
    tally: inside === outside ? "tie" : "off",
    qualified_nonrecourse: qnr,
    other_nonrecourse: other,
  };
}

export const BASIS_PARTNERS = PARTNERS.map(partner);

export function basis(view: BasisView, partnerId?: string | null): TaxDepthBasisOut {
  const partners =
    partnerId === undefined || partnerId === null
      ? BASIS_PARTNERS
      : BASIS_PARTNERS.filter((p) => p.partner_id === partnerId);
  return {
    view,
    partners,
    reconciled: 4,
    inside_total: "17914500",
    outside_total: "17943095",
    section_754: "open",
  };
}
