import type { EngagementSummaryOut } from "@abacus/api-client";

/** The API's engagement type (F-03-T12: the 14 types; `audit` is now `fs_audit`). */
export type EngagementType = EngagementSummaryOut["type"];

/** The types offered when creating an engagement, in plain words. The other types arrive with
 * their service lines (tax, CAS, attest, notices, advisory). */
export const ENGAGEMENT_TYPES: [EngagementType, string][] = [
  ["fs_audit", "Financial statement audit"],
  ["ebp_audit", "Employee benefit plan audit"],
  ["review", "Review"],
  ["compilation", "Compilation"],
  ["preparation", "Preparation"],
  ["agreed_upon_procedures", "Agreed-upon procedures"],
];

const OTHER: Partial<Record<EngagementType, string>> = {
  soc1: "SOC 1",
  soc2: "SOC 2",
  readiness: "Readiness",
  internal_audit: "Internal audit",
  tax_compliance: "Tax compliance",
  cas_monthly_close: "Monthly close",
  notice_response: "Notice response",
  advisory: "Advisory",
};

export function typeLabel(type: string): string {
  return (
    ENGAGEMENT_TYPES.find(([value]) => value === type)?.[1] ??
    OTHER[type as EngagementType] ??
    type
  );
}
