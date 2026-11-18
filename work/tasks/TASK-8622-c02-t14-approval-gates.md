---
id: TASK-8622
title: "C-02-T14: Notification kinds and human-gate registrations for close approvals"
spec: SPEC-700
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: c02-t14-approval-gates
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: C-02-T14
---

## Objective
Spec section: docs/plan/epics/C-02.md §4.6, §4.7. The C16 kinds and C13 gates: entry approval requested reaches the named approver's HOME-02 queue and bell; walled or removed recipients receive nothing.

## Plan (red)
1. The seven C16 kinds were registered in C-02-T02 (DEC-5501): entry_approval_requested, posting_failed, posting_batch_posted, package_client_approved, tax_handoff_received/superseded, vendor_form_uploaded; the request event now carries proposed_entry_id, recipient_user_ids and by_user, matching the catalogue's subject and _listed recipients.
2. adjustments/approval_gates.py: GateSource proposed_entry, DF-25 kind final_approval, read proposed_entry.read, open for every Review required entry (role manager), recomputed on proposed_entry.approval_requested and the new proposed_entry.approval_decided (emitted by every close-approval write).
3. review/gates.py C13_EVENTS gains the two events; adjustments.api registers the source at import.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5622). Partial: posting_batch_ready, close_package_release and information_return_batch_approval gates register with their services (C-02-T19 posting batch, T29 package, T45 information returns), whose subjects do not exist yet; their kinds are already catalogued. The projector re-authorises recipients (walls, removals) at fan-out and read, so the walled case needs no owner code. Gates and tests run once at the S50 end pass (build first, test last).
