---
id: TASK-8437
title: "A-09-T27: rest: a deliverable request emails the component auditor"
spec: SPEC-658
acceptance_criteria: [AC-3]
risk_zone: amber
status: in-review
branch: s48r-deliverable-request
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T27
---

## Objective
A-09-T27 named the deliverables request but sent no email. A request now sends the firm's component_deliverable_request template to the auditor's engagement partner contact, as the requesting person, under component_deliverable.manage; with no published template the send is recorded blocked and the request stands.

## Plan (amber)
1. Register the component_deliverable_request email template (third_party, room link, firm-editable; DB wording via ADM-10).
2. request_deliverable sends after the insert through communications.api.send_templated with authority component_deliverable.manage (a new SEND_AUTHORITIES pair) and the route's Idempotency-Key; audit request_sent or request_blocked.
3. Unit test for both outcomes and the authority pair.

## Progress log
- `2026-11-17` — Built (S48 rest, DEC-5426). The wording is firm content (imported per environment); code supplies organisation_name, deliverable_title and due_date, the system the firm name and portal link. Gates and tests run once at the S48 end pass (build first, test last).
