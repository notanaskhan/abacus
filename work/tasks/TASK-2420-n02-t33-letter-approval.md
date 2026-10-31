---
id: TASK-2420
title: N-02-T33 Letter approval, send and amend
spec: SPEC-000  # the backlog row; N-02 §3.11, §4.2, C7 §2, C11 AC-15/AC-19, C13
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T33
branch: s19-n02-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Request approval with C13 gate `letter_partner_approval`; approval by the engagement partner with
a fresh second factor under the human-gate pattern, storing the content hash (any later change
returns the letter to Draft); Send creating a C7 draft from the `engagement_letter` source
(client, then firm countersigner, email-code identity); lock on `envelope.completed`; addendum
versions; G1's date before the letter date.

Acceptance: "Daniel Reyes approves at 8:32 AM, a later fee edit voids the approval, and Send opens
a SIG-02 draft ordered Owen Calder then Daniel Reyes."

## Plan (red)
- Migration `0563_letter_approval` (on 0562; expand-only): approval request columns,
  `final_document_version_id`, the guard trigger replaced so only the approving person's own
  transaction moves a version to `partner_approved`; `letter.approved` in
  `abacus_human_only_actions()` (63). Downgrade restores 0561's 62 and drops the columns.
- `engagements/letter_flow.py`: request, approve, send, amend, C7 subscriptions, C13 due gates,
  the envelope prefill and pre-send check. Ports: `letter_render.py` (finaliser, locker) and
  `letter_send.py` (sender), filled by `reporting` and `signatures` (ADR-008).
- `letters.py`: addenda keep kind and amended version; no edit once an envelope is drafted;
  `allowed_actions` per status.
- `signatures/sources.py`: the letter source drafts from the approved version; check and sender.
- `review/engagement_gates.py` (protected) and `gates.C13_EVENTS`; `notifications/catalogue.py`.
- Routes live behind `engagements.letter_composer` (send also needs `signatures.envelopes`).
- Regenerated: `kernel/_human_only_actions.py`, `packages/api-client`, `error-codes.yaml`.
- ENG-04: the request names the version (If-Match).
- Tests: `tests/integration/test_n02t33_letter_approval.py` (run at the end review).
- Rollback: flag off; the migration's downgrade.

## Progress log
- `2026-10-31` — Built on `s19-n02-t33` off main 7d4def8e5. DEC-1468. Found while building:
  T09's letter source took the engagement as its record; it is now the approved version, so the
  pre-send check can refuse a replaced letter. Approve UI and consent rows are N-02-T35's.
