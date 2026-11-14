// The close shell's seed (C-01-T12): Copperleaf Coffee Roasters, Inc.'s August 2026 close as the
// CLS-02 record bar and Summary rail draw it (C-01 §3 US-1.3; SPEC-655 AC-7). Every figure is the
// handoff's: Open Issues 7, Documents in Binder 58, Accounts Reconciled 9 of 21, Past Due 4 days,
// Tess Moreno "Active" with 2 requests pending. The full Copperleaf figure book (22 closes, the
// tiles 3 · 11 · 5 · 3, the runs, the plan) is C-01-T13's.
import type { CloseSummaryOut } from "@abacus/api-client";
import { entityIdOf, slugOfClient } from "./clients";
import { slugOf } from "./people";
import { stableId } from "./prng";

const CLIENT = "Copperleaf Coffee Roasters, Inc.";
const person = (name: string, initials: string) => ({
  user_id: stableId(`user:${slugOf(name)}`),
  name,
  initials,
});

export const CLOSE_IDS = {
  july: stableId("close:copperleaf:2026-07"),
  august: stableId("close:copperleaf:2026-08"),
  september: stableId("close:copperleaf:2026-09"),
} as const;

const ENGAGEMENT_ID = stableId("engagement:copperleaf:2026-close");

export function copperleafAugust(): CloseSummaryOut {
  return {
    close_id: CLOSE_IDS.august,
    engagement_id: ENGAGEMENT_ID,
    engagement_name: "2026 Close",
    client_id: stableId(`client:${slugOfClient(CLIENT)}`),
    client_entity_id: entityIdOf(slugOfClient(CLIENT), CLIENT),
    client_name: CLIENT,
    period: "2026-08",
    previous_period_close_id: CLOSE_IDS.july,
    next_period_close_id: CLOSE_IDS.september,
    status: "in_progress",
    on_hold: false,
    on_hold_reason: null,
    attest: false,
    preparer: person("Raj Malhotra", "RM"),
    reviewer: person("Priya Raman", "PR"),
    open_issues: 7,
    documents_in_binder: 58,
    accounts_reconciled: 9,
    accounts_total: 21,
    due_on: "2026-09-08",
    days_past_due: 4,
    requests_publish_on: "2026-09-01",
    plan_version: 3,
    run_no: 2,
    sync: null,
    portal: {
      contact_name: "Tess Moreno",
      portal_status: "active",
      requests_pending: 2,
      messages: { target: "INB-04", label: "Messages" },
    },
    in_review_blocked_by: "accounts_not_reconciled",
    planned_links: [{ target: "HOME-03", label: "Past Due" }],
    allowed_actions: ["close_run.start", "close_run.retry"],
    row_version: 1,
  };
}
