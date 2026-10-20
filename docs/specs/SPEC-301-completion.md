---
id: SPEC-301
title: "Completion: deficiency severity concluded by the engagement partner, proposed adjusting entries balanced by code, and the representation list with what still lacks one"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-050]
related_specs: [SPEC-043, SPEC-300]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
The plan's AUD-15 severity (AU-C 265), AUD-16 proposed entries, and the AUD-21 representation list, first slice (S10-1 and parts of S10-2 and S10-5, without the agent or the portal).
- **Severity.** A senior, manager or partner proposes a finding's severity: deficiency, significant deficiency or material weakness. Only the engagement partner concludes it, with a rationale. A manager or the partner records when the concluded deficiency was communicated, and to whom.
- **Proposed entries.** The team proposes AJE-n and RJE-n entries, whose debits must equal their credits (checked by code). A manager or the partner approves an entry, then records the client's answer: accepted, or declined and passed. The firm never posts.
- **Representations.** The team keeps a list of specific representations, each linked to a finding or entry or standing alone. Code lists the concluded deficiencies and passed entries that no representation covers yet, and the passed entries the attached summary includes.

## 2. Acceptance criteria
- **AC-1** Proposing severity (`finding.propose_severity`: senior, manager, partner): insert-only, and the newest proposal counts.
- **AC-2** Concluding severity (`finding.conclude_severity`: the engagement partner only): needs a rationale; insert-only, and the newest conclusion counts.
- **AC-3** Recording communication (`finding.communicate`: manager, partner):
  - only once a severity has been concluded (otherwise `not_concluded`);
  - the status is communicated when a communication is newer than the conclusion.
- **AC-4** Proposing an entry (`adjustment.propose`: senior, manager, partner):
  - 2–50 lines, each one-sided and non-negative, with debits equal to credits (`completion_invalid` otherwise);
  - numbered per engagement and kind.
- **AC-5** The entry's events:
  - approve (`adjustment.approve`: manager, partner), once;
  - then the client's answer (`adjustment.record_response`), once: accepted, or declined, which shows as "Passed".
- **AC-6** The entries are listed with their lines, total, status and approver.
- **AC-7** Representations (`representation.edit`: senior, manager, partner):
  - add one, linked or not;
  - remove one: it's taken off the list but the record stays.
- **AC-8** Code lists the gaps: concluded deficiencies and passed entries without a representation. It also lists the passed entries for the attached summary.
- The agent is denied every action here, and independence is required.

## 3. Data
All tables are insert-only, with forced RLS:
- `finding_severities`
- `finding_communications`
- `adjustments`
- `adjustment_lines`
- `adjustment_events`
- `representations`
- `representation_removals`

## 4. Out of scope
- The agent's proposals.
- Client approval in the portal (POR-08).
- SUM rollover and iron-curtain views.
- Generating the letter (needs firm wording, R11).
- Governance letters.
- The decision card (SHL-11) as a shared service.
