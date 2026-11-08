// EBP-08 (A-05-T52): Northwind's participant accounts at Thu Sep 24, 2026, verbatim from the handoff
// spec, in A-05-T46's shapes. Rows crossfoot and the Total foots: 14,228,500 + 1,318,300 +
// 2,116,650 - 812,650 - 38,400 = 16,812,400; transfers net to 0; brokerage 924,300 + 612,450 +
// 68,250 = 1,605,000. All names fictional. Dev and test only.

import type { AccountRollforwardOut, SdbaOut, VestingOut } from "@abacus/api-client";

export const EBP08_WORK_ITEM = "6f1c2a90-0000-4000-8000-0000000000e8";

const ACTIVE = {
  status: "active", participants: 219, beginning: "11612300.00", contributions: "1318300.00",
  earnings: "1716000.00", distributions: "-104600.00", fees: "-29200.00", transfers: "-871900.00",
  ending: "13640900.00", crossfoots: true,
}; // prettier-ignore
const TERMINATED = {
  status: "terminated", participants: 82, beginning: "2616200.00", contributions: "0.00",
  earnings: "400650.00", distributions: "-708050.00", fees: "-9200.00", transfers: "871900.00",
  ending: "3171500.00", crossfoots: true,
}; // prettier-ignore
const TOTAL = {
  status: "total", participants: 301, beginning: "14228500.00", contributions: "1318300.00",
  earnings: "2116650.00", distributions: "-812650.00", fees: "-38400.00", transfers: "0.00",
  ending: "16812400.00", crossfoots: true,
}; // prettier-ignore

export const ROLLFORWARD: AccountRollforwardOut = {
  groups: [ACTIVE, TERMINATED],
  total: TOTAL,
  ties: [
    { key: "net_trust_assets", expected: "16812400.00", actual: "16812400.00", ties: true },
    { key: "contributions_allocated", expected: "1318300.00", actual: "1318300.00", ties: true },
    { key: "distributions", expected: "812650.00", actual: "812650.00", ties: true },
    { key: "fees", expected: "38400.00", actual: "38400.00", ties: true },
  ],
  forfeiture_account: "0.00",
  transfers_net_zero: true,
  engine_version: "1",
  inputs_hash: "0".repeat(64),
  allowed_actions: ["field.sign_off"],
};

export const SDBA: SdbaOut = {
  rows: [
    { security_type: "Common stocks", market_value: "924300.00" },
    { security_type: "Exchange-traded funds", market_value: "612450.00" },
    { security_type: "Money market sweep", market_value: "68250.00" },
  ],
  total: "1605000.00",
  per_trust: "1605000.00",
};

function terminated(key: string, name: string, on: string, years: string) {
  return {
    participant_key: key, name, termination_on: on, years_of_service: years, vested_pct: "100",
    agrees: true, identifier_mask: null,
  }; // prettier-ignore
}

export const VESTING: VestingOut = {
  rows: [
    terminated("p1", "Dmitri Volkov", "Feb 14, 2025", "3.4"),
    terminated("p2", "Noor Siddiqui", "Apr 4, 2025", "2.3"),
    terminated("p3", "Wallace Grant", "May 9, 2025", "5.1"),
    terminated("p4", "Corinne Blake", "Jul 31, 2025", "11.2"),
    terminated("p5", "Siobhan Kelly", "Sep 19, 2025", "8.7"),
    terminated("p6", "Esther Kim", "Nov 21, 2025", "6.0"),
  ],
  forfeitures_arising: "0.00",
};
