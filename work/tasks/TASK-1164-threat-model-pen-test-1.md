---
id: TASK-1164
title: Threat-model refresh for pen test #1 — scope table and rows for sign-in, portal hosts, uploads, citations and the viewer, compliance records and outbound messages (Q-03-T018)
spec: SPEC-051
acceptance_criteria: [AC-2]  # Q-03 D3: the model names every surface in scope; N's review is the row's acceptance
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T018
branch: s7-small-items-incidents
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The model names every surface in the pen-test scope and N has approved it by Fri Feb 5." Q-03 D3; ADR-064.

## Plan (amber zone, a document)
- `docs/architecture/ai-threat-model.md`: a pen test #1 scope table (surface, built or stub or not built on `main`, boundaries, rows); new rows for staff and portal sign-in (AU), portal hosts and the role union (PO), uploads, citations and the viewer (EV), legal holds, incidents, exports and trace export (CR), follow-ups and notification email (OB); coverage moved from Planned to Tested where the control landed; new gaps; a review row.
- Public-repo rule: no exploit detail, no credentials, no environment addresses, no firm or person names.
- No code. Rollback: revert the file.

## Progress log
- 2026-10-24: refreshed. Every cited test path checked to exist. Not built and marked so: firm export (Q-02-T43), firm-owned custom domains (P-11, RB-21), the live portal drop and the C4 viewer (stubs). Status `in-review`: N's approval (due Fri Feb 5, 2027) is the acceptance and is not this session's to give. Re-run before the build pin, since R-01, P-03 and Q-02-T43 may land first.
- 2026-10-24: second pass after the S7 batch is TASK-1178 (same row, Q-03-T018).
