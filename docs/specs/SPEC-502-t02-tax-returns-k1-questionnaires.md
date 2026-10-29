---
id: SPEC-502
title: "Tax returns v1, K-1 packages and questionnaires, S16 contract window: stubs, protected bundle rows, vocabulary, consumer tests, screen contracts, migration and fixtures (T-02-T01 to T08)"
status: in-progress
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-231, ADR-300]
related_specs: [SPEC-500, SPEC-501]
created: 2026-10-29
updated: 2026-10-29
---

> **Instructions for coding agents**
> - `docs/plan/epics/T-02.md` is the plan of record (§3 to §5); where they differ, the epic wins and this spec is corrected.
> - Accrued shows engine values only from approved imports (ADR-231); figures are TRI. Agents propose; humans decide (ADR-005). Every test names the acceptance criterion it proves.

## 1. Summary
T-02 is the tax practice board and the return workspace (TAX-01 to TAX-03), K-1 packages and their release to the portal (TXP-12, POR-13) and questionnaires (organizers, team questions and inquiries; POR-05). S16 opens the window with contracts and the data model.

## 2. Acceptance criteria
**Protected bundle rows (T-02-T03).**
- **AC-1** The matrix holds `tax_return.read_metadata`, `.assign`, `.status_change`, `k1_package.read`, `.share_internal`, `.release` (fresh MFA), `.resend`, `k1_recipient.review_details`, `questionnaire_template.import`, `.read`, `.publish` (fresh MFA), `questionnaire.create`, `.ask`, `.read`, `evidence.resolve_duplicate` and the portal `portal_questionnaire.*` and `portal_k1.*` rows; every firm write denies the agent, the system and client principals; the generated I-AGENT-NEVER suite covers `k1_package` and `questionnaire_template`.
- **AC-2** Flags `tax.returns_v1`, `tax.k1_release`, `questionnaires.v1`, `evidence.duplicate_review` exist and default off; K1RELEASE-001 refuses `k1_releases` outside `tax/k1_release.py`.

**Vocabulary (T-02-T04).**
- **AC-3** The glossary has T-02's rows (tax return, questionnaire, question, answer, K-1 package, K-1 recipient, K-1 hand-off, recipient details change, engine summary); the status registry has `tax_return` (13 codes with Draft, Working, Ready and Issues contexts), `k1_package` (7, client words), `questionnaire`, `recipient_details_change` and `k1_handoff`.

**Tax-returns v1 stub (T-02-T01).**
- **AC-4** `GET /v1/tax-returns`, `/summary`, `/{id}`, `/{id}/overview`, `/{id}/intake`, `POST /v1/tax-returns:bulk-assign`, `/{id}/assignments`, `/{id}/transitions` declare their actions and are stubs behind `tax.returns_v1`; figures are TRI and names confidential; `docs/contracts/tax-returns.md` exists.

**K-1 and questionnaire stubs (T-02-T02).**
- **AC-5** The K-1 package, recipient-details, questionnaire-template, questionnaire and portal questionnaire and K-1 routes of T-02 §4.3 declare their actions and are stubs behind their flags; box lines are TRI; `docs/contracts/k1-packages.md` and `questionnaires.md` exist.

**Consumer tests (T-02-T05).**
- **AC-6** Consumer suites assert C19's consent summary and TRI tags, C21's `due_dates_for` and the BH-TAX-02 standard kind, C7's envelope summary, and C3's `final_approval` sign-off kind.

**Screen contracts (T-02-T06).**
- **AC-7** `docs/screens/TAX-01.md`, `TAX-02.md`, `TAX-03.md`, `TXP-12.md`, `POR-05.md`, `POR-13.md` exist with states, personas, clocks, parity tiers, deviations and AVOID lists.

**Migration (T-02-T07).**
- **AC-8** `tax_returns` gains the v1 columns (nullable or defaulted; expand only), `tax_return_status_events` is insert-only and immutable, `return_engine_summaries` is a tenant table with forced RLS; `tax/status.py` holds the transition table and `tax.api.apply_transition` refuses a transition the table does not allow.

**Fixtures (T-02-T08).**
- **AC-9** Fixture seed rows and per-artboard scenarios for the six screens with personas `nora-calloway` and `pell-street-member`, and footing tests.

**Practice-board read models (T-02-T09).**
- **AC-10** `GET /v1/tax-returns/summary` answers per-status tiles for the year (the latest on file by default), open (every status but `filed` and `accepted`), done (`filed`, `accepted`), extended and office totals; at Brightwater Hale TY2025 they foot to 79 open, 145 done, 224 total.
- **AC-11** Rows, tiles, totals and office counts are wall-safe: a return whose work item the viewer may not see (`visible()`, walls included) is absent from every one, with no hidden count (INV-3, DEC-43).
- **AC-12** `GET /v1/tax-returns` filters by status, review level, form, office, partner (signer), preparer, due within n days (business time) and `q` (client name, case-folded substring); sort is an allowlist (`extended_due` default, `client`; anything else 422); `group_by=office` orders by office first. Rows carry people chips (initials and name), the sync chip and tags `ext`, `on_hold`.
- **AC-13** `POST /v1/tax-returns:bulk-assign` (Idempotency-Key) assigns through `engagements.api.assign_work_item` and answers `assigned` and `refused` (any return the viewer can't see or engagements refuses), never a reason.
- **AC-14** G-01's office fact `tax_returns` (the latest year's returns per office) and the C15 projection `tax_return` (form and year; metadata only) are registered.
