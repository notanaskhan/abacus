// AUD-10 (A-04-T37): Northwind's service organizations and Keystone's SOC 1 Type 2, verbatim from the
// handoff: gap Oct 1 to Dec 31, 2025 = 92 days; 2 of 6 CUECs evidenced. Names are fictional. Dev and
// test only.

import type { ServiceOrganizationOut, SocReportOut } from "@abacus/api-client";
import { stableId } from "./prng";

export const AUD10_REPORT = stableId("soc-report:keystone:2025");
export type Aud10Variant = "a" | "b" | "e";

function org(
  name: string,
  services: string,
  relevant: boolean,
  evidence_type: ServiceOrganizationOut["evidence_type"],
  status: ServiceOrganizationOut["status"],
  soc: string | null = null,
): ServiceOrganizationOut {
  return {
    allowed_actions: [],
    evidence_type,
    id: stableId(`service-org:${name}`),
    name,
    relevant,
    row_version: 1,
    services,
    soc_report_id: soc,
    status,
    subservice_orgs:
      soc === null ? [] : [{ name: "Ridgeway Data Services", treatment: "carve_out" }],
  };
}

export function aud10Orgs(variant: Aud10Variant = "a"): { items: ServiceOrganizationOut[] } {
  return {
    items: [
      org(
        "Keystone Retirement Services",
        "Recordkeeping",
        true,
        "soc1_type2",
        variant === "b" ? "bridge_letter_received" : "gap_found",
        AUD10_REPORT,
      ),
      org("Harborline Trust Company", "Trustee & custody", true, "certification", "certification_accepted"),
      org("PayGrid Payroll", "Payroll", true, "tested_directly", "no_reliance"),
      org("Summit Plan Administrators", "TPA", false, "none", "not_relevant"),
    ],
  };
}

const CUECS: readonly [number, string, boolean][] = [
  [1, "Send accurate and timely census and pay data", false],
  [2, "Remit contributions on time and agree them to payroll", false],
  [3, "Review participant statements and Keystone reports", false],
  [4, "Limit sponsor-portal access to authorized staff", true],
  [5, "Approve hardship distributions and loans per the plan", true],
  [6, "Review SOC reports and bridge letters", false],
];

export function aud10Report(variant: Aud10Variant = "a"): SocReportOut {
  return {
    allowed_actions: [],
    cuecs: CUECS.map(([n, text, done]) => ({
      control_activity_id: null,
      n,
      page_citation_id: null,
      status: done ? "evidenced" : "evidence_missing",
      text,
    })),
    cuecs_evidenced: 2,
    evidence_version_id: stableId("evidence-version:keystone-soc1"),
    exceptions: [
      {
        co_ref: "CO 7 Distributions",
        description: "1 of 40 distributions lacked a second approval",
        impact: "low",
        impact_rationale: "distributions are tested substantively (EBP-05)",
        routed_ref: null,
      },
      {
        co_ref: "CO 10 Logical access",
        description: "2 of 25 terminated users were removed 11 and 14 days late",
        impact: variant === "e" ? "high" : "low",
        impact_rationale: "neither user had access to Northwind's plan",
        routed_ref: variant === "e" ? "F-07" : null,
      },
    ],
    gap: { bridged: variant === "b", days: 92, end: "2025-12-31", start: "2025-10-01" },
    id: AUD10_REPORT,
    objectives_relevant: 9,
    objectives_total: 12,
    opinion: "unmodified",
    period_end: "2025-09-30",
    period_start: "2024-10-01",
    reliance_card_id: null,
    reliance_state: "pending",
    report_date: "2025-11-14",
    report_type: "type_2",
    row_version: 1,
    service_auditor_name: "Larch & Whitney LLP",
    service_organization_id: stableId("service-org:Keystone Retirement Services"),
  };
}
