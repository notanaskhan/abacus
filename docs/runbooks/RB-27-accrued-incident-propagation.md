---
id: RB-27
title: Accrued-originated incident touching firm data
owner: builder
owning_epic: Q-02
alarms: []
last_rehearsed: never
rehearse_by: 2027-04-16
---
# RB-27 · Accrued-originated incident touching firm data (72 hours)

| Field | Value |
|---|---|
| Owner | builder (Q-02-T51; register and propagation Q-02-T33, AC-39) |
| Severity range | SEV1 to SEV2 |
| Linked from | RB-08 (cross-firm exposure), RB-29 (integrity), any SEV1 touching firm data |
| Clock | the DPA's notice: within **72 hours of Accrued confirming** the incident (`confirmed_at`); each firm's own FTC clock (30 days from its discovery) runs in its register |
| Kill switches that apply | none (this is notification, not containment: contain first under the runbook that found it) |
| Rehearse by | R2 (tabletop on staging with the synthetic firms) |

When Accrued itself has a security incident that touched a firm's data, every touched firm gets an entry in its own incident register (ADM-06) with Accrued's facts, and the firm's Qualified Individual and admins are told, within 72 hours of confirmation. The firm then runs its own clock and notices; Accrued never notifies the firm's clients.

## 1. Recognise it
The incident runbook that found the problem (RB-08, RB-29, RB-12, a provider notice) has confirmed that firm data was touched, and which firms. Write the confirmation time down: it starts the 72 hours.

## 2. Contain
Under the runbook that found it. Do not start propagation until the set of touched firms is known; a later firm gets its own run.

## 3. Preserve
Keep the evidence the finding runbook preserved (vault `V-…`). The facts file below holds no client data, names or values: identifiers, kinds and counts only.

## 4. Assess
Write `facts.json` outside the repository: `title` (Confidential, never printed), `event_kind`, `discovered_at`, `confirmed_at` (ISO 8601 with an offset), `consumers_affected` (a count), `unencrypted` (true or false). Agree the firm list (ids) with the other founder.

## 5. Notify (the 72 hours)
1. A platform staff member with MFA puts a staff-issuer token in `ABACUS_STAFF_TOKEN` (environment only).
2. Dry run: `make incident-propagate REF=ACC-<yyyy>-<nnn> FIRMS=<id>,<id> FACTS=<path>/facts.json STAFF=<staff id> REASON="<one line>" DRY_RUN=1`. Every firm must exist and have `compliance.incidents` on; fix any refusal (turn the flag on for that firm through `make flag`, with the other founder's approval).
3. Run it without `DRY_RUN`. `IncidentPropagation` writes each firm's entry as the system (`source = 'accrued'`, `dpa_notice_at` set) and sends `incident_from_accrued` to the firm's QI and admins.
4. `make incident-status REF=ACC-<yyyy>-<nnn>`: every firm listed, none failed. A failed firm: read the reason, fix, run again for that firm only (a propagation is idempotent per firm and ref).
5. Counsel's notice to each firm's contact (vault template) goes out by the 72-hour mark, outside the product.

## 6. Recover
Firms read the entry on ADM-06 and run their own decision (the "Notify FTC" two-person decision is theirs). Answer firm questions with facts from `facts.json`, never with another firm's data.

## 7. Verify
Each firm's register shows the entry with Accrued's facts and `dpa_notice_at` within 72 hours of `confirmed_at`; `incident-status` shows no failed firm; the audit trail has the system-attributed entry per firm.

## 8. Review
Blameless review (ADR-097) linking this runbook; update the facts schema or the steps if anything slowed the 72 hours.

## Rehearsal log
| Date | Where | Who | Result |
|---|---|---|---|
