// Q-02-T38: compliance-kernel v1.1 fixtures for G-02's ADM-06 and Q-05's later reads
// (docs/contracts/compliance-kernel.md), derived from the seed and the ADM-06 handoff, never
// invented: INC-2026-005 (ADM-06 a, d), discovered Thu Sep 10, 2026 at 2:14 AM CT, "0 confirmed",
// "Day 4 of 30 · notify by Oct 10" at E0 (Mon Sep 14, 2026, 9:24 AM CT); the monthly export history
// (ADM-06 c: Sep 1 386 GB, Aug 1 371 GB, Jul 1 359 GB, each at 2:00 AM CT); and Felix Andersen's
// request "Waiting for approval · Margaret Okonkwo" (ADM-06 g). The backend half is
// backend/tests/contracts/compliance_kernel/. Brightwater Hale, synthetic.
import type { FirmExportOut, FirmExportPageOut, IncidentOut } from "@abacus/api-client";
import { stableId } from "./prng";

const FELIX = { user_id: stableId("user:felix-andersen"), display_name: "Felix Andersen" };
const MARGARET = { user_id: stableId("user:margaret-okonkwo"), display_name: "Margaret Okonkwo" };
const GB = 1000 ** 3;
/** E0 in UTC: Mon Sep 14, 2026, 9:24 AM CDT. */
export const COMPLIANCE_E0 = "2026-09-14T14:24:00Z";
/** A placeholder digest: the manifest's real SHA-256 is computed when the archive is built. */
const MANIFEST = "0".repeat(64);

export const INC_2026_005: IncidentOut = {
  id: stableId("incident:INC-2026-005"),
  ref: "INC-2026-005",
  title: "Credential-stuffing attempts against client portal sign-in",
  event_kind: "credential_attack",
  discovered_at: "2026-09-10T07:14:00Z",
  consumers_affected: 0,
  unencrypted: null,
  notification_event: false,
  ftc_notify_by: "2026-10-10",
  clock_day: 4,
  clock_days: 30,
  source: "firm",
  accrued_ref: null,
  accrued_confirmed_at: null,
  dpa_notice_at: null,
  created_at: "2026-09-10T07:14:00Z",
};

/** A monthly scheduled export at 2:00 AM CDT (07:00 UTC) on the 1st; its 7 days are over at E0. */
function monthly(day: string, sizeGb: number): FirmExportOut {
  const at = `${day}T07:00:00Z`;
  const plus = (hours: number): string =>
    new Date(Date.parse(at) + hours * 3_600_000).toISOString().replace(".000Z", "Z");
  return {
    id: stableId(`firm-export:${day}`),
    status: "expired",
    scope: "all",
    origin: "scheduled",
    requested_by: FELIX,
    requested_at: at,
    approver: MARGARET,
    decided_at: at,
    ready_at: plus(1),
    available_until: plus(7 * 24),
    size_bytes: sizeGb * GB,
    manifest_sha256: MANIFEST,
  };
}

export const EXPORT_REQUESTED: FirmExportOut = {
  id: stableId("firm-export:requested:2026-09-14"),
  status: "awaiting_approval",
  scope: "all",
  origin: "on_demand",
  requested_by: FELIX,
  requested_at: COMPLIANCE_E0,
  approver: MARGARET,
  decided_at: null,
  ready_at: null,
  available_until: null,
  size_bytes: null,
  manifest_sha256: null,
};

export const EXPORT_HISTORY: readonly FirmExportOut[] = [
  monthly("2026-09-01", 386),
  monthly("2026-08-01", 371),
  monthly("2026-07-01", 359),
];

/** ADM-06 a and c (no request yet) or g (Felix has asked; Margaret must approve). */
export function firmExportPage(requested: boolean): FirmExportPageOut {
  return { items: requested ? [EXPORT_REQUESTED, ...EXPORT_HISTORY] : [...EXPORT_HISTORY] };
}
