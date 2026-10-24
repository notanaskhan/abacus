---
id: TASK-1140
title: S7 pen-scope security files and independent AC suites (Q-03-T012, T013, T014, T015; Q-02-T36; P-04-T13; P-06-T17; P-01-T15; F-04-T36)
spec: SPEC-002
acceptance_criteria: [AC-4, AC-5, AC-7]
risk_zone: red
status: in-progress
epic: Q-03
plan_key: Q-03-T012; Q-03-T013; Q-02-T36; P-04-T13; P-06-T17; P-01-T15; F-04-T36; Q-03-T014; Q-03-T015
branch: s7-security-tests
test_author: ayushkbhatia
test_session: 2026-10-24, branch s7-security-tests (one clean session per suite, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-24
updated: 2026-10-24
---

## Objective
- **Q-03-T012:** "The file is a required check by Fri Feb 12, 2027 and fails on a seeded wall bypass in each of the seven surfaces."
- **Q-03-T013:** "Each hostile sample is refused or quarantined with the documented status and none reaches preview or extraction."
- **Q-02-T36:** "The suite fails against seeded violations of I-RETENTION-FLOOR and I-HOLD and passes on main."
- **P-04-T13:** "AC tests pass and fail when any human-only CHECK or insert-only trigger is removed, and the Undo conformance suite fails for a route that skips the window or the grant void."
- **P-06-T17, P-01-T15, F-04-T36, Q-03-T014, Q-03-T015:** as their rows.

## Plan (red zone; tests only)
- **Files:** `backend/tests/security/test_walls_and_need_to_know.py` (T012), `backend/tests/security/test_upload_hostile_files.py` (T013), then one independent file per remaining row.
- **Migrations, registry, flags:** none. Product code changes only where a test exposes a small local defect, each logged in `docs/quality/escaped-defects.md`; anything larger is held with `xfail(strict=True)` citing this task.
- **Boundary:** `create_app()` over HTTP on the migrated testcontainer Postgres, seeded as the superuser; public `api.py` functions where a row names one. Expectations from specs, contracts, ADRs and decisions only (ADR-078).
- **Rollback:** delete the test files; revert the logged fixes.

## Q-03-T012: walls and need to know
Seven surface probes (records, lists, search, counts, notifications, exports, agent sessions), each returning what it found of Ashford for Lena Park; the holding tests assert none, with Granite as the control. Plus two sweeps over the served route table (every GET naming Ashford's engagement, client, version or run reads exactly as an id that never existed; no list route carries Ashford), ADR-024 metadata-only for an off-team admin and `security_admin`, a walled admin, and `test_d1_a_seeded_wall_bypass_fails_every_surface` (the wall lifted in the database; every probe must report Ashford). 61 tests, all pass.

- **Defect ED-017 (fixed):** every trace export answered 500. C6 §7 records `Ref(sha256, rows)` and the unit of work's `Ref` refused a key containing a digit; nothing on `main` had ever exported a trace. `Ref` keys may now carry digits after the first letter (`kernel/uow/__init__.py`).
- **Noted, not a defect:** the C4 viewer family (`/v1/evidence-versions/{id}/viewer`, `/search`) is a contract stub answering 501 before any authorisation when `evidence.viewer_v1` is on; it reads the same for a walled id and an unknown one, so the sweep passes. The live viewer (P-03) must authorise first; the sweep will hold it to that.

## Q-03-T013: hostile files
Through the item upload and the inbox over HTTP (compose S3 image with Object Lock), then the `upload_processing` stages (extract, check, preview) run as activities on the stored version. EICAR (plain, inside an XLSX, in a PNG+ZIP polyglot), ratio, size, entries and nested bombs, a scan of the inbox, over 50 MB, seven types outside DEC-58 (c), empty, four polyglots, a password-protected PDF (unreadable, no pages: SHL-08 D), a PDF with JavaScript, HEIC, a malformed PDF (unreadable, never a worker failure), and the control (an ordinary statement is extracted and paged). 28 tests: 18 pass, 10 held.

- **ED-018 (open):** uploads stop at 25 MB, not DEC-58 (c)'s 50 MB. A body past the edge's request limit answers 413 `payload too large` from the middleware (ADR-152, Q-01-T16) before the route's 422 `upload_too_large`; the >50 MB test accepts either, both refuse before storage. Held: the route limit, the protected edge limit and the extraction memory limits move together.
- **ED-019 (open):** `sniff` keeps any text as `text/csv` and passes OLE and macro workbooks, so HTML, SVG, JavaScript, `.doc` and `.xlsm` are stored. Held: a type-policy change (declared type and name against the bytes) that reaches every test uploading text.
- **ED-020 (open):** HEIC is refused, contrary to DEC-58 (c).
- **ED-021 (open):** a PDF with JavaScript is extracted and previewed. Held: needs a scanner rule or a PDF policy decision.
- **Spec drift:** SPEC-029 §7 says 25 MB; DEC-58 (c) (later) says 50 MB. The test follows DEC-58.

## Q-02-T36: retention and holds
`backend/tests/integration/backfill/test_q02t36_retention_and_holds.py`, 16 tests, all pass: AC-31 below floor (422, nothing changes; the floor itself saves; a manager is refused), AC-32 lock at or after the policy expiry (floor, and the firm's longer policy), an anchor extends and never shortens, `retention.extended` as the system, AC-33 seal manifests, consent and signature evidence in COMPLIANCE (delete refused even with the bypass), no records bucket answers 503 for a record and for an anchor, AC-34 staff and stale MFA refused, audited as the person, AC-35 two overlapping holds through `LegalHoldApply` and `LegalHoldRelease` on a Temporal dev server (lifting one leaves both objects held and S3-held; at zero the S3 hold comes off), `hold_not_active`, AC-36 inheritance in the uploader's transaction (and a hold on another client covers nothing here), AC-37 fail closed with no check and for an unknown version. Seeded violations: an object's lock shortened in S3 behind the product fails the retention probe; hold counts dropped and the S3 hold switched off fail the hold probe. Floors are seeded through `retention.import_set` and `publish_set` (two staff), as the platform staff routes do. No defect found.

## P-04-T13: the four P-04 migrations and the shared Undo suite
- `backend/tests/integration/test_p04t13_review_schema_independent.py`, 16 tests, all pass: RLS forced on all 19 tables of 0093, 0094, 0095 and 0102, and the app role in one firm sees none of another's; agent, system, support and policy actors refused by a CHECK on all five decision tables; a person claiming someone else's id refused (the CHECK binds `app.actor_id`); UPDATE and DELETE refused to the app role on every decision table, and by trigger to the owner too; every insert-only table has UPDATE and DELETE revoked or trigger-refused; one decision per card; the proposal and suggestion Undo windows and "after a consumed grant"; a grant settles once and nothing else on it moves. On a private database, dropping the human-only CHECKs and disabling the decision triggers (or granting UPDATE on `sign_offs`) makes the probes fail. Up/down/up: the session database is provisioned through schema_check's round trip before these run.
- **Shared C3 Undo conformance suite:** `backend/tests/contracts/undo/test_undo_contract.py` (a package, with its own private database, so it can register cases; the plan named `tests/contracts/test_undo_contract.py`, and importlib mode needs the package for the registry). Six contract tests per registered route plus three self-checks; 19 pass. Registered: `evidence_review_decision` (P-01-T15), `request_item_send` and `binder_publish` (P-06-T17). Follow-up send Undo is not registered yet (it needs a published binder with recipients and a template; recorded under P-06-T17).
- **Defect ED-022 (fixed):** another partner could undo a binder publish inside the window; `undo_publish` now refuses anyone but the publisher (`requests/binders.py`), as the send Undo already did.
- **Spec gap:** the review-decision Undo by another person answers 403 `forbidden`; P-01 AC 3.1.4 says only the decider may undo but names no code, and C3's 409 `undo_window_closed` for "another person" is the proposal route's. The suite accepts either refusal with nothing written; one code across Undo routes is a decision for the main session.

## P-06-T17: binders and requests
`backend/tests/integration/backfill/test_p06t17_binders_requests.py`, 13 tests, all pass: G3 (pbc refused with `binder_gate_unmet` when the firm requires a letter and none is recorded, nothing held; intake publishes), every binder transition and its refusals (publish twice, unpublish without or with a blank reason, unpublish twice, republish), idempotent publish and send (same response, one audit row, one held outbox event), send needs a due date, `model_text_not_permitted` with nothing sent and then sent once edited (DV-11), only a never-sent draft is deleted (and the database refuses soft-deleting a sent one), DEC-38 (senior and staff cannot publish, staff cannot create, partner publishes; staff and above send; a firm member off the team cannot), INV-3 (a walled member gets 404 on binder, rows, publish and send), T11 (walled binders absent from rows, total and counts, no hidden word), INV-4 (the client preview never shows a draft). The publish and send Undo (voided grant sends nothing, effect started, same person) are registered in the shared C3 suite (P-04-T13 above).

- **Defect ED-023 (fixed):** a retried send or return-to-client answered 500: the idempotent replay skipped `authorise`, so the guard refused it. Both routes authorise first now (`lifecycle.check_item_action`). The follow-up send routes have the same shape and are not yet tested (follow-up Undo is not registered either: it needs a published binder with recipients and a template).
- **Contract note:** `binder_not_draft`, `binder_not_published` and `request_already_sent` carry a `facts.status` the contract's table does not show; additive, tests compare `detail`.
- **ED-010 (already open)** explains why G3 is met with no letter while the firm's letter policy is off; the G3 test turns `require_letter` on.

## Progress log
- 2026-10-24: T012 written and green (61 passed); ED-017 fixed with it.
- 2026-10-24: T013 written: 18 pass, 10 held as ED-018 to ED-021.
- 2026-10-24: Q-02-T36 written: 16 pass.
- 2026-10-24: P-04-T13 written: 16 + 19 pass; ED-022 fixed.
- 2026-10-24: P-06-T17 written: 13 pass; ED-023 fixed.
