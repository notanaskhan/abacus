// EBP-07 (A-05-T58): Northwind's draft Form 5500 tie-out at Thu Sep 24, 2026, verbatim from the
// handoff, on `Form5500Out`. Figures foot: 5500 net assets 16,812,400 = 14,228,500 + 2,583,900; the
// only differences are the 48,600 receivable (15,060 / 33,540). All names are fictional. Dev and
// test only.

import type {
  Form5500Out,
  Form5500RowOut,
  PartIvLineOut,
  Schedule4iOut,
} from "@abacus/api-client";

export const EBP07_WORK_ITEM = "6f1c2a90-0000-4000-8000-0000000000e7";
export const EBP07_DRAFT_VERSION = "6f1c2a90-0000-4000-8000-0000000005e7";
export type Ebp07Variant = "a" | "d" | "e";

let n = 0;
function line(code: string, caption: string, fs: string, form: string | null): Form5500RowOut {
  n += 1;
  const id = `6f1c2a90-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
  const off = form === null ? fs : (BigInt(fs) - BigInt(form)).toString();
  const ties = off === "0";
  return {
    id,
    line_code: code,
    caption,
    fs_amount: `${fs}.00`,
    f5500_amount: form === null ? null : `${form}.00`,
    difference: ties ? null : `${off}.00`,
    classification: ties ? "tie" : "reconciling_item",
    note_ref: ties ? null : "Note 8",
    match_id: form === null ? null : `ev:${EBP07_DRAFT_VERSION}#p2:${code}`,
  };
}

export const ASSET_LINES: Form5500RowOut[] = [
  line("1b(1)", "Employer contributions receivable", "15060", null),
  line("1b(2)", "Participant contributions receivable", "33540", null),
  line("1c(8)", "Participant loans", "312400", "312400"),
  line("1c(9)", "Common/collective trusts", "1163480", "1163480"),
  line("1c(13)", "Registered investment companies", "13731520", "13731520"),
  line("1c(15)", "Other — self-directed brokerage", "1605000", "1605000"),
  line("1f", "Total assets", "16861000", "16812400"),
  line("1l", "Net assets", "16861000", "16812400"),
];

export const INCOME_LINES: Form5500RowOut[] = [
  line("2a(1)(A)", "Employer contributions", "392100", "377040"),
  line("2a(1)(B)", "Participant contributions", "878400", "844860"),
  line("2a(1)(C)", "Rollovers", "96400", "96400"),
  line("2b(1)(E)", "Interest on participant loans", "17800", "17800"),
  line("2b(6)", "Common/collective trusts", "41280", "41280"),
  line("2b(10)", "Registered investment companies", "1893410", "1893410"),
  line("2b(2)–(5)", "Brokerage income", "164160", "164160"),
  line("2d", "Total income", "3483550", "3434950"),
  line("2e(1)", "Benefit payments (incl. loan offsets 14,850)", "812650", "812650"),
  line("2i(1)", "Professional fees", "6000", "6000"),
  line("2i(2)", "Contract administrator fees", "32400", "32400"),
  line("2j", "Total expenses", "851050", "851050"),
  line("2k", "Net income", "2632500", "2583900"),
];

// Part IV, every line 4a to 4m as the handoff's b artboard lists them. Code checks 4a against the
// late remittances (DEC-2820); the others are the draft's answers, not checked by code.
const NO = { draft_answer: "no", draft_amount: null, consistency: "not_checked" } as const;

function partIv(variant: Ebp07Variant): PartIvLineOut[] {
  const late = variant === "e";
  return [
    {
      line: "4a",
      draft_answer: late ? "no" : "yes",
      draft_amount: late ? null : "33540.00",
      consistency: late ? "inconsistent" : "consistent",
      basis: "EBP-04 finding",
    },
    {
      line: "4b",
      ...NO,
      basis:
        "participant loans are excluded from 4b; the plan holds no other loans (EBP-05, EBP-06)",
    },
    { line: "4c", ...NO, basis: "" },
    { line: "4d", ...NO, basis: "late contributions belong on 4a" },
    {
      line: "4e",
      draft_answer: "yes",
      draft_amount: "500000.00",
      consistency: "not_checked",
      basis: "EBP-01",
    },
    { line: "4f", ...NO, basis: "" },
    { line: "4g", ...NO, basis: "" },
    { line: "4h", ...NO, basis: "" },
    {
      line: "4i",
      draft_answer: "yes",
      draft_amount: null,
      consistency: "not_checked",
      basis: "EBP-06",
    },
    { line: "4j", ...NO, basis: "" },
    { line: "4k", ...NO, basis: "" },
    { line: "4l", ...NO, basis: "" },
    { line: "4m", ...NO, basis: "" },
  ];
}

// The 4i schedule by code (EBP-07 c): seven holdings issued by parties in interest, cost omitted
// for the participant-directed ones; total 16,812,400 ties to the draft's line 1c.
function held(identity: string, value: string, mark: "*" | "", directed = true) {
  return {
    mark,
    identity,
    description: "",
    cost: directed ? null : "0.00",
    cost_omitted: directed,
    current_value: value,
  };
}

export function ebp07Schedule4i(): Schedule4iOut {
  return {
    rows: [
      held("KRS 500 Index Fund", "6120450.00", "*"),
      held("KRS Target 2035 Fund", "2384910.00", "*"),
      held("KRS Target 2045 Fund", "2915330.00", "*"),
      held("KRS Bond Index Fund", "1408220.00", "*"),
      held("KRS International Index Fund", "902610.00", "*"),
      held("Harborline Stable Value Fund", "1163480.00", "*"),
      held("Self-directed brokerage accounts (BrokerWindow)", "1605000.00", ""),
      held("Participant loans", "312400.00", "*", false),
    ],
    total: "16812400.00",
    draft_total: "16812400.00",
    ties: true,
    inputs_hash: "d".repeat(64),
  };
}

export function ebp07View(variant: Ebp07Variant = "a"): Form5500Out {
  if (variant === "d") {
    return { draft_received: false, lines: [], rows: [], part_iv: [], allowed_actions: [] };
  }
  const rows = [...ASSET_LINES, ...INCOME_LINES];
  return {
    draft_received: true,
    draft_id: "6f1c2a90-0000-4000-8000-0000000005d7",
    evidence_version_id: EBP07_DRAFT_VERSION,
    lines: rows.map((r) => ({
      key: `h.${r.line_code}`,
      label: r.caption,
      amount: r.f5500_amount,
      status: r.classification,
      note: r.note_ref ?? null,
    })),
    rows,
    part_iv: partIv(variant),
    allowed_actions: ["ebp_form5500.key", "ebp_form5500.send_note", "ebp_form5500.remind"],
  };
}
