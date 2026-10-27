---
id: TASK-1447
title: Export sheet design follow-up and UI, record-mode dialogs (phase, release, archive) with MFA step-up, 10-s Undo toast and status polling (A-01-T24)
spec: SPEC-344
acceptance_criteria: [A-01-T24]
risk_zone: green
status: in-review
epic: A-01
plan_key: A-01-T24
branch: s11-engagements
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Hannah exports with step-up, sees Packaging then Ready, and Undo within 10 s cancels the export."

## Plan
- `domain/audits/exports.ts` (generated client: create with Idempotency-Key, undo, list, 3-s
  status poll while open and moving, download as a file), `ExportSheet.tsx`, `RecordDialogs.tsx`
  (phase, release, archive), `AuditActions.tsx` (the "···" menu and the overlays), wired into
  AUD-02's canvas header; words in `messages.ts`.
- Fixture routes `fixtures/handlers/exports.ts` (each status read moves one step), mounted for
  Northwind in `auditHandlers`.
- Design follow-up recorded in docs/screens/AUD-02.md (DV-9), DEC-541, DF row requested.
- Tests: `domain/audits/ExportSheet.test.tsx`.

## Progress log
- 2026-10-27: built; Playwright skipped (chromium mismatch).
