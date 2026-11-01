---
id: TASK-2518
title: T-01-T36 8879 amount binding and drift relock (I-8879-DRIFT)
spec: SPEC-501  # T-01 §3.12; efile-record
acceptance_criteria: [AC-10]  # and T-01 §3.12
risk_zone: red
status: done
epic: T-01
plan_key: T-01-T36
branch: s20b-t01-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
8879 amount binding and drift relock in tax/filing.py: the `tax_return` envelope source for C7
(8879 family and state forms from engine PDFs, signers from the filing unit with the form_8879
policy), efile_amount_bindings from the approved checkpoint at envelope creation, recheck on
checkpoint.approved and reference_set.published using platform.api.pub1345_tolerances,
signatures marked superseded_by_change through C7 and the gate relocked; the system may only
relock, never unlock.

Acceptance (backlog row): "A later import moving AGI by 51 dollars supersedes the signed Feld 8879
and relocks transmission, while a 50-dollar move does not."

## Plan (red)
- Migration **0524** `efile_amount_bindings` (revises 0523): figures (TRI) with SHA-256 and the
  tolerances' reference-set version; the app may set `superseded_at`/`superseded_reason` once; a
  guard trigger refuses clearing them, any other change and deletes. Forced RLS.
- `tax/filing.py` (red): the `tax_return` envelope source (Form 8879 + TR-579-IT from the engine
  PDFs by their fingerprint, the filing unit's signers with KBA, parallel), `draft_envelope`
  (approved packet first, then C7's `create_draft`, then the binding), `drift` (strictly beyond
  the tolerance; a figure appearing or disappearing relocks), `recheck` (system; supersedes the
  binding, audits, emits `efile.relocked`, calls C7's `supersede_for_amount_change`).
- `tax/api.py`: the source registered; `checkpoint.approved` and `reference_set.published`
  subscribe (the latter composed with due dates').
- Route `POST /tax-returns/{id}/efile-envelope` live; TAX-12's read model shows the envelope and
  whether its binding is superseded.
- **Stacked** on T-01-T35 (the approved packet; 0524 chains after 0523).
- Rollback: `tax.delivery_efile`; 0524 is expand-only.

## Not done (open)
- `efile_relocked` notification to the team and `client_service`: the event is emitted; the
  notifications catalogue kind and its copy wait for T-01-T37's notification set.
- The full draft path (filing-unit contacts, the form 8879 set and the signature policy) is
  proven by C7's and T-01-T10's suites; this suite proves the relock and the gate order.

## Decisions
DEC-1566.

## Progress log
- `2026-10-31` — Built on `s20b-t01-t36` (stacked on `s20b-t01-t35`). test_t01t36: 6 passed.
