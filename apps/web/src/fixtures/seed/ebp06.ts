// EBP-06 (A-05-T40): Northwind's investments at Thu Sep 24, 2026, verbatim from the handoff, on A-05-
// T39's `InvestmentsOut`. Figures foot: six funds 14,895,000 and 12,683,000; 16,500,000 and 13,940,000
// with BrokerWindow; Level 1 15,336,520 + NAV 1,163,480. All names are fictional. Dev and test only.

import type { CertificationPointOut, InvestmentRowOut, InvestmentsOut } from "@abacus/api-client";

export const EBP06_WORK_ITEM = "6f1c2a90-0000-4000-8000-0000000000e6";
export type Ebp06Variant = "a" | "b" | "c" | "d" | "e";
type Level = InvestmentRowOut["level"];

function row(key: string, label: string, boy: string, eoy: string, level: Level): InvestmentRowOut {
  return {
    key, label, level, trust_boy: boy, trust_eoy: eoy, tb_boy: boy, tb_eoy: eoy, ties: true,
    off_by: "0.00",
  };  // prettier-ignore
}

const FUNDS: InvestmentRowOut[] = [
  row("krs_500", "KRS 500 Index Fund", "5102300.00", "6120450.00", "level1"),
  row("krs_2035", "KRS Target 2035 Fund", "2011640.00", "2384910.00", "level1"),
  row("krs_2045", "KRS Target 2045 Fund", "2388970.00", "2915330.00", "level1"),
  row("krs_bond", "KRS Bond Index Fund", "1276090.00", "1408220.00", "level1"),
  row("krs_intl", "KRS International Index Fund", "868000.00", "902610.00", "level1"),
  row("stable", "Harborline Stable Value Fund (CIT)", "1036000.00", "1163480.00", "nav"),
  row("broker", "Self-directed brokerage — BrokerWindow", "1257000.00", "1605000.00", "level1"),
];
const NOTES = row("notes", "Notes receivable from participants", "288500.00", "312400.00", "not_certified");

const POINT_TEXT: readonly [string, string][] = [
  ["qualifying_institution", "Harborline Trust Company, state-chartered trust company examined by the Illinois DFPR (qualifying institution, 29 CFR 2520.103-8)"],
  ["complete_and_accurate", "\"complete and accurate\""],
  ["period", "Jan 1 – Dec 31, 2025"],
  ["signer_and_date", "Vice President, Retirement Trust Operations, Sep 11, 2026"],
  ["covers", "investments"],
  ["not_covered", "participant loans → tested in EBP-05"],
];

function points(answer: CertificationPointOut["answer"]): CertificationPointOut[] {
  return POINT_TEXT.map(([key, proposed_answer]) => ({
    key,
    proposed_answer,
    citation_id: null,
    answer,
    note: null,
  }));
}

export function ebp06View(
  variant: Ebp06Variant = "a",
  layer: InvestmentsOut["layer"] = "final",
): InvestmentsOut {
  const unadjusted = layer === "unadjusted" || variant === "b";
  const receivable: InvestmentRowOut = {
    key: "1200",
    label: "Contributions receivable",
    level: "other",
    tb_eoy: unadjusted ? "0.00" : "48600.00",
  };
  const pending = variant === "c";
  return {
    layer,
    rows: [...FUNDS, NOTES, receivable],
    investments_eoy: "16500000.00",
    investments_boy: "13940000.00",
    level1_eoy: "15336520.00",
    nav_eoy: "1163480.00",
    net_assets: unadjusted ? "16812400.00" : "16861000.00",
    tb_balanced: true,
    py_ties: true,
    points: points(pending ? "not_evaluated" : "evaluated"),
    hold_reason: pending ? "certification_unevaluated" : null,
    unevaluated: pending ? 6 : 0,
    engine_version: "1",
    inputs_hash: "c".repeat(64),
    allowed_actions: [],
  };
}
