// G-02-T07: the governance fixtures foot to the shared golden
// (backend/tests/golden/scenario/brightwater_hale/governance_e0.json), which the backend's golden
// test reads too: Day 4 of 30 with notice by Oct 10, 18,406 events with 4 of 1,962 via Agent,
// the 20,020.00 Copperleaf footing, 46 of 46 enrolled (41 of 46 on Jan 11), v1 to v3.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { validateResponse } from "./schema-check";
import { AUDIT_TOTAL, COPPERLEAF_VALUES, VIA_AGENT_TOTAL, feed, page } from "./seed/audit-log";
import { EXPORT_HISTORY, INC_2026_005 } from "./seed/compliance";
import {
  AI_POLICY_VERSIONS,
  INC_2026_003,
  INC_2026_004,
  LAST_SUPPORT_SESSION,
  SIGN_IN_E0,
  SIGN_IN_JAN_11,
  WISP,
} from "./seed/governance";

interface Golden {
  incidents: {
    ref: string;
    title: string;
    discovered_on: string;
    clock_day?: number;
    ftc_notify_by?: string;
  }[];
  audit_log: { total: number; via_agent_shown: number; via_agent_total: number; rows: number };
  copperleaf: {
    amounts: string[];
    total: string;
    not_included: { amount: string; routed_to: string };
  };
  mfa: {
    e0: { enrolled: number; seats: number };
    jan_11_2026: { enrolled: number; seats: number };
  };
  sso: { enforced_on: string; enforced_by: string };
  ai_policy_versions: {
    version: number;
    published_on: string;
    published_by: string;
    approved_by: string;
  }[];
  exports_gb: Record<string, number>;
  support_session: { on: string; engineer: string };
  wisp: { name: string; approved_on: string; controls_evidenced: number; controls_total: number };
}

const GOLDEN = JSON.parse(
  readFileSync(
    join(
      dirname(fileURLToPath(import.meta.url)),
      "../../../../backend/tests/golden/scenario/brightwater_hale/governance_e0.json",
    ),
    "utf8",
  ),
) as Golden;
const cents = (amount: string): number => Math.round(Number(amount) * 100);

describe("governance fixtures and the E0 golden", () => {
  it("INC-2026-005 reads Day 4 of 30, notify by Oct 10; 004 and 003 are closed, not events", () => {
    const [i5, i4, i3] = GOLDEN.incidents;
    expect([INC_2026_005.clock_day, INC_2026_005.ftc_notify_by]).toEqual([
      i5?.clock_day,
      i5?.ftc_notify_by,
    ]);
    expect([INC_2026_004.title, INC_2026_004.discovered_at.slice(0, 10)]).toEqual([
      i4?.title,
      i4?.discovered_on,
    ]);
    expect([INC_2026_003.title, INC_2026_003.discovered_at.slice(0, 10)]).toEqual([
      i3?.title,
      i3?.discovered_on,
    ]);
    for (const closed of [INC_2026_004, INC_2026_003]) {
      expect(closed.notification_event).toBe(false);
    }
  });

  it("the audit log reads 18,406 events and 4 of 1,962 via Agent", () => {
    expect(AUDIT_TOTAL).toBe(GOLDEN.audit_log.total);
    expect(VIA_AGENT_TOTAL).toBe(GOLDEN.audit_log.via_agent_total);
    const rows = feed("default");
    expect(rows).toHaveLength(GOLDEN.audit_log.rows);
    expect(rows.filter((r) => r.actor.kind === "via_agent")).toHaveLength(
      GOLDEN.audit_log.via_agent_shown,
    );
    expect(
      validateResponse("GET", "/v1/audit-events", page(rows, AUDIT_TOTAL, "default", true)),
    ).toEqual([]);
  });

  it("the Copperleaf batch foots to 20,020.00 with 14,900.00 left out for Priya Raman", () => {
    const amounts = (COPPERLEAF_VALUES.rows ?? []).map((r) => r.amount ?? "");
    expect(amounts).toEqual(GOLDEN.copperleaf.amounts);
    expect(amounts.reduce((n, a) => n + cents(a), 0)).toBe(cents(GOLDEN.copperleaf.total));
    const [left] = COPPERLEAF_VALUES.not_included ?? [];
    expect(left?.amount).toBe(GOLDEN.copperleaf.not_included.amount);
    expect(left?.routed_to?.display_name).toBe(GOLDEN.copperleaf.not_included.routed_to);
  });

  it("46 of 46 enrolled at E0, 41 of 46 on Jan 11; SSO enforced Jan 12 by Felix", () => {
    expect([SIGN_IN_E0.mfa_enrolled, SIGN_IN_E0.seats]).toEqual([
      GOLDEN.mfa.e0.enrolled,
      GOLDEN.mfa.e0.seats,
    ]);
    expect([SIGN_IN_JAN_11.mfa_enrolled, SIGN_IN_JAN_11.seats]).toEqual([
      GOLDEN.mfa.jan_11_2026.enrolled,
      GOLDEN.mfa.jan_11_2026.seats,
    ]);
    expect(SIGN_IN_E0.sso_enforced_on).toBe(GOLDEN.sso.enforced_on);
    expect(SIGN_IN_E0.sso_enforced_by?.display_name).toBe(GOLDEN.sso.enforced_by);
  });

  it("AI policy v1 Jan 5, v2 Jan 9, v3 Jan 14: Margaret publishes, Daniel approves", () => {
    expect(
      AI_POLICY_VERSIONS.map((v) => ({
        version: v.version,
        published_on: v.published_on,
        published_by: v.requested_by.display_name,
        approved_by: v.approved_by.display_name,
      })),
    ).toEqual(GOLDEN.ai_policy_versions);
    for (const v of AI_POLICY_VERSIONS) expect(v.approved_by).not.toEqual(v.requested_by);
  });

  it("exports, the support session and the WISP agree", () => {
    const gb = Object.fromEntries(
      EXPORT_HISTORY.map((e) => [e.requested_at.slice(0, 10), (e.size_bytes ?? 0) / 1000 ** 3]),
    );
    expect(gb).toEqual(GOLDEN.exports_gb);
    expect([LAST_SUPPORT_SESSION.on, LAST_SUPPORT_SESSION.engineer]).toEqual([
      GOLDEN.support_session.on,
      GOLDEN.support_session.engineer,
    ]);
    expect([WISP.name, WISP.approved_on, WISP.controls_evidenced, WISP.controls_total]).toEqual([
      GOLDEN.wisp.name,
      GOLDEN.wisp.approved_on,
      GOLDEN.wisp.controls_evidenced,
      GOLDEN.wisp.controls_total,
    ]);
  });
});
