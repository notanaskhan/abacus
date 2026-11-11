---
id: TASK-6737
title: "A-07-T47: fixture-to-live swap for AUD-24 and AUD-25 (polling, invalidation, refusal words, run status)"
spec: SPEC-314
acceptance_criteria: [A-07 F6, F7, F11]
risk_zone: green
status: in-review
branch: s35b-a07-t47
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-11
updated: 2026-11-11
plan_key: A-07-T47
---

## Objective
On staging Hannah Leclerc's AUD-19 updates within 10 s of Dana Kowalski signing, and every A-07
screen runs with VITE_FIXTURES unset.

## Plan
- `apps/web/src/domain/audits/completionLive.ts` (new) has:
  - `useLiveRelease` and `useLiveArchive`: reads every 10 s (`LIVE_POLL_MS`), every 2 s while the person's release or lock runs (`RUN_POLL_MS`), until the server shows G8 or the seal;
  - each post carrying an Idempotency-Key;
  - `invalidateCompletion`: every completion read is invalidated on a mutation, and nothing else;
  - `refusalWords`: `archived`, `gates_not_met`, `content_changed`, `mfa_required` and the rest in words;
  - `asksForStepUp`: a stale second factor opens the shell's step-up.
- `screens/AUD-24/IssuanceLive.tsx` and `screens/AUD-25/ArchiveLive.tsx` (new): the server's
  gates, rows, clock, checklist and binder; the release and lock behind the design's
  attestation, shown only with the server's action and a bound host; "Releasing…" and
  "Locking…" while the workflow runs.
- `screens/AUD-02/completionLetters.tsx`: AUD-24 and AUD-25 open live inside the cockpit with
  `audits.report_release` and `audits.archive` (lazy chunks; fixture builds unchanged).
- Tests: `completionLive.test.ts`, `IssuanceLive.test.tsx`, `ArchiveLive.test.tsx`.

## Partials (flagged)
- **AUD-18, AUD-19 and AUD-21 can't swap yet:** their reads (`GET …/eqr`, `…/completion`,
  `…/subsequent-events`, `…/legal-letters`, `…/going-concern`, `…/representation-letter`) and
  the rep letter's send are still 501 stubs at the server. AUD-19 can't update within 10 s of
  Dana's signature until `GET …/completion` reads the projector. That is backend work, not this
  row's.
- The staging check (10 s on staging, every screen with `VITE_FIXTURES` unset) waits on staging.
- The refusal sentences are this task's own: the handoff names no words for these codes
  (DEC-3303).
- Compose status polling for AUD-21 waits on its live read (above). AUD-22 and AUD-23 already
  read live and now invalidate through `invalidateCompletion` when their mutations land.

## Progress log
- `2026-11-11` — Built; the new web tests pass (AUD-02, AUD-24, AUD-25 and the domain suite).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3303 | Polling intervals, the invalidation set, refusal words, flags that open AUD-24/25 live | no |
