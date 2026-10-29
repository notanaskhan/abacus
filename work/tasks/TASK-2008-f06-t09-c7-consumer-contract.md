---
id: TASK-2008
title: F-06-T09 C7 and C5 consumer contract tests for the signing kit
spec: SPEC-400
acceptance_criteria: [F1]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T09
branch: s15n-f06-t09
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Consumer contract tests in the provider's CI: the C7 envelope view and signing session (and the
portal scope its page and session routes run under) mapped to EnvelopeVM.

Acceptance: "A breaking change to any C7 or C5 field that EnvelopeVM maps fails the provider's CI
before the signing kit breaks."

## Built
- `apps/web/src/domain/signing/envelope-vm.ts`: `toEnvelopeVM` (C7 `PortalEnvelopeView` →
  `EnvelopeVM`), `outcomeOf` (DF-11's `paper_form_follows` → `verification_failed`),
  `DECLINE_CODES` (the kit's four reasons → C7 codes), `pagePath`. Typed by the generated client.
- `backend/tests/contracts/c7_n02/test_f06_consumer.py`: pins every field, enum and route the
  mapper and the POR-06 container read (36 cases; ran once, 36 passed).
- `envelope-vm.test.ts`: the mapping, on a fixture typed by the generated client (not run yet).

## Progress log
- 2026-10-29: built. Found while mapping: C7's `outcome` (`signed`, `declined`, `abandoned`) and the
  kit's (`verification_failed`, `declined`, `expired`, `voided`) differ; the mapper derives the
  kit's from `paper_form_follows`, `outcome` and the row status (no C7 change needed).
