---
id: TASK-2210
title: K-02-T08 firm standards service
spec: SPEC-500
acceptance_criteria: [AC-27, AC-28, AC-29, AC-30, AC-31, AC-32, AC-33, AC-34]
risk_zone: amber
status: done
epic: K-02
plan_key: K-02-T08
branch: s17-k02-t08
created: 2026-10-30
updated: 2026-11-01
---

## Objective
The C21 part B service in `methodology`: create, assign owner, draft from current, PATCH draft
with If-Match, discard, publish with `effective_from` on or after today and fresh MFA, computed
Superseded, version diff, audit and outbox events, the examples registration slot filtered by
`visible()` with no hidden counts, K-01 knowledge-item and change-log registration, C15 search
registration (metadata only) (K-02 §3 F3, §4.4, §4.5).

Acceptance (backlog row): "Priya Raman publishes Draft v3 effective Oct 1, 2026 on the demo
clock, v2 stays current until then, the audit event names her, and Daniel Reyes gets 403
not_standard_owner."

## Plan (amber)
- `methodology/models.py`: ORM for the four 0401 tables (two mixins).
- `methodology/standards.py` (new): the service; errors `owner_not_partner`, `standard_key_taken`,
  `draft_exists`, `no_current_version`, `not_draft`, `stale_version`, `payload_invalid`,
  `effective_from_backdated`, `effective_from_not_after_current`, `not_standard_owner`
  (catalogued); `current_version`; `register_standard_examples`.
- `methodology/standards_routes.py` (new): the router moves out of the contract; import and
  export stay 501 (K-02-T11). Publish runs through `idempotent()`.
- `methodology/standards_catalog.py` (new): KNW-01 `firm_standards` provider and the C15
  `firm_standard` projection, registered from `methodology.api`.
- `methodology/events.py`: `firm_standard.published`, `threshold_policy.published`.
- Audit actions added to the reviewed fallback list (`activity_reviewed.py`).
- No migration (0401 holds the tables), no matrix or flag change. Stacked on K-02-T07 so the C21
  test file and the generated client move once.
- Tests: `tests/integration/test_k02t08_firm_standards.py` (HTTP, Postgres, demo clock); the C21
  stub suite moves the standards reads and lifecycle to live.
- Rollback: revert; the routes return to 501.

## Acceptance
| Check | Test |
|---|---|
| Publish v2 effective Oct 1; v1 current until then; audit names Priya; Daniel 403 | `test_ac27_*` |
| Drafts partners' only | `test_ac28_*` |
| Agent refused and audited | `test_ac29_*` |
| draft_exists, stale_version, payload_invalid, not_draft | `test_ac30_*` |
| Effective-date rules | `test_ac31_*` |
| Diff and discard | `test_ac32_*` |
| Examples slot | `test_ac33_*` |
| current_version, owner must be a partner | `test_ac34_*` |

## Progress log
- 2026-10-30: built in S17 Lane 2 on K-02-T07; tests written, run in the end review.
- Not done here: `firm_standard_version.published` in the protected human-only list (DEC-1256).
- 2026-11-01: merged to main in #778 (e1e0edd0a).
