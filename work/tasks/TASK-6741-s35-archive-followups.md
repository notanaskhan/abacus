---
id: TASK-6741
title: "S35 follow-ups: the archive load under the worker, a reproducible 10:05 export, Granite Peak's audit committee and release"
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-progress
epic: A-07
branch: s35c-archive-followups
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-11
updated: 2026-11-11
plan_key: S35-followups-1
---

## Objective
Three partials left by A-07-T41/T43 (TASK-6735, TASK-6736):

- **AC-1.** The `archive` slice loads to Fri Jan 15, 2027 at 3:00 PM with the relay and the worker
  running (`make dev`): the release at 10:07, its final render, the archive, the Dec 3 lock and
  seal, and the Jan 15 addition.
- **AC-2.** `make fixtures SNAPSHOT=2026-10-09T10:05` gives the same file on every load: no
  wall-clock value in the also-required rows.
- **AC-3.** Granite Peak (A2) has its own audit committee and releases on Tue Oct 27, 2026: drafted
  and approved statements, the AU-C 260 letter sent to the committee, the bring-down, the signed
  letter, the final review and the release.

## Plan
- Also-required values: `fs_approved` reads the approved statement version's number
  (`reporting.api.fs_approved_version_no`); `bring_down` carries no time (the run's finish is the
  database clock). No migration.
- Granite Peak: a `governance_body_seeded` setup event with its own body and member; the loader's
  governance handlers take the body from `archive_slice.BODIES`; two new handlers draft and approve
  statements through `reporting.api`.
- Under the worker: the TB version-1 auto-mapping starts a mapping the loader also starts
  (suppress `MappingExists*`); a final review closes G5 before each release.
- Checklist sign-off: `completion_facts.sign_offs` leaves out the checklist's own row (signing it
  changed it); the loader signs the checklist last, on a rebuilt projection (a projection still in
  flight from the letter's signing changed it after the sign-off).
- Rollback: revert the branch; no migration, no flag.

## Progress log
- 2026-11-11: also-required values made deterministic; Granite Peak body and release events and
  handlers; mapping suppresses; final-review events. Load under the worker reached the 10:07
  release and was refused on G5 (the checklist stale at L1/L2).
- 2026-11-11: two causes of the stale checklist, both fixed: its own sign-off counted as changed
  in the `sign_offs` item (DEC-3306), and the letter's signing projected after the re-sign.
- 2026-11-11: past G5, the release found no draft render: the scenario now renders the draft
  (AUD-23 "Generate", the manager) after the EP's L4. The release workflow then failed
  `grant_refused`: the worker read wall time, so the 10:07 grant was expired. The loader stands
  the firm's demo clock at the event before handing the release or the lock to the worker, and a
  `failed:` workflow result stops the load (it had read as success).
- 2026-11-11: the release's record step failed the deliverables CHECK: it published C10 kind
  `audit_report` (C11's document kind); C10's is `auditor_report`. Fixed in `release.py`. No test
  had recorded an in-app release against Postgres before this load.
- 2026-11-11: then the `report_releases` insert: one parameter (`:by`) fed `released_by` (uuid)
  and `actor_id` (text), "inconsistent types deduced" on Postgres. Split. A scan of the
  assurance module's actor-id inserts found no other reused parameter of two types.
- 2026-11-11: then `phase_gate_unmet`: the phase move's G8 read only SPEC-314's `releases` and the
  external record, never A-07's `report_releases` written in the same unit. It now reads it.
- 2026-11-11: the release recorded (G8). Then `report.released` retried forever with
  `MissingAuditEvent`: both its consumers open the archive, and the second commits a unit that
  records nothing. The same trap waited in the Form 5500 row and the AU-C 265 due date on any
  redelivery. Each step now skips when it changes nothing (a read first, or a rolled-back unit).
- 2026-11-11: Granite Peak: the going-concern decision needs a rationale (scenario data now
  carries the partner's); the final review signed as Northwind's team (signers now by role on
  the audit's own team); then G5 asked for L5 on findings, materiality and the FS package, and
  Granite has no EQR: G5 now owes L5 only where an EQR is on the team (DEC-3306), with a unit test.
- 2026-11-11: Granite Peak's senior drew its sample, so its L2 was refused (R-SO-3, never the
  preparer): the loader's signer for L2/L3 now skips the target's preparers up the team's roles,
  and L1 is the preparer's when they are on the team. A resumed load skips a handler that failed
  after committing part of its work (its trace exists): only a fresh load proves the path.
- 2026-11-11: Northwind and Granite Peak both released under the worker. Two more: the release
  row's `released_at` was the column default (wall clock), so a synthetic firm's release, and the
  archive's documentation date after it, fell on the day of the load: it is now written from the
  business clock. Lakeshore's report choice was the partner's, which the matrix refuses
  (`report.draft`: manager or senior): its manager, Omar Haddad, drafts (DEC-3306).
- 2026-11-11: Lakeshore's manager confirms independence before drafting (the matrix's
  `independence: required`). Then the Dec 3 lock request: "Binder index complete" never held after
  a readiness run, because the run built the index and then recorded its own run log, which grew
  section G. The run now records first (counting its own log) and builds the index after.
- 2026-11-11: Dec 3 lock decided, but the seal could not write its manifest: no records bucket on
  a local run (`records_bucket` unset; the writer fails closed, rightly). `make dev`'s LOCAL_ENV
  now names `abacus-records`, and `abacus_tools.local.evidence_bucket` creates it with Object Lock
  when named; tests keep it unset (their fail-closed checks stand). Locked and sealed at 4:18 PM.
- 2026-11-11: the Jan 15 addition: its memo could not be stored on the archived engagement, so no
  addition could exist. Ayush chose to allow it (DEC-3308): `store_addition_evidence` under
  `archived_write = archive_addition`, migration 0814 (the two evidence triggers, and the
  addition's `id` insert grant, also missing), an integration test on the trigger definitions.
  The loader's pending-addition query read a `status` column that does not exist.
- 2026-11-11: S36 merged first (main c9ebfb0eb, head 0813): at rebase the addition migration
  becomes 0814 on 0813, and DEC-3308's text names 0814.
- 2026-11-11: the fresh load passes to Jan 15, 2027 3:00 PM under the worker (AC-1, AC-3):
  Northwind released Oct 9 10:07, locked and sealed Dec 3 4:18 PM, its addition approved; Granite
  Peak released Oct 27. Two exports of 10:05 still differed (AC-2): AUD-22's row id and send time,
  AUD-23's version time and hash, AUD-24's gate hash. The send and version times now default to
  `abacus_now()` (0814), and the export stands in governance and report-version ids and hashes
  with no id above them (`gate_hash` added). No committed fixture had such a hash, so none moves.
