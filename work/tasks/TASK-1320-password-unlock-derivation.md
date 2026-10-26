---
id: TASK-1320
title: Password unlock as a derivation (P-03-T19; C4 §3.5, SPEC-322 F5)
spec: SPEC-322
acceptance_criteria: [AC-31, AC-32, AC-33, AC-34, AC-35]
risk_zone: red
status: in-review
epic: P-03
plan_key: P-03-T19
branch: s10b-pii-unlock-viewer
created: 2026-10-26
updated: 2026-10-26
---

## Objective
`POST /v1/evidence-versions/{v}/unlock` answers 501. Make it open a password-protected PDF with
the password a person types, without changing the evidence: one isolated child decrypts, reads
the word layer (w2), scans it for PII (d2) and renders masked pages (v3/m2), and the results land
as insert-only derived records under an `evidence_derivations` row. The unlocked copy goes through
exactly the same word layer, PII scan and masker as any upload, so the viewer's masked pages, the
offshore text view and search read it as they read an ordinary upload. The password is a
`SecretStr`, never logged, stored, sent to Temporal or echoed. Five failed attempts per person per
version in 15 minutes, then 429.

## Plan
- **Child** (`unlock.derive_unlocked`, module level, picklable): `remove_password` → if
  unlocked, `words.extract_words` on the plain bytes → per page `pii.detect_on_page`,
  `across_break`, `page_dangles` (the same loop as `pii_scan_upload`) → `previews.render_masked`
  with every detected box. Returns the outcome, the pages, the found regions and the masked PNGs.
  The decrypted bytes never leave the child. Any exception in the child becomes `damaged` (no
  message crosses the boundary).
- **Service** (`unlock.unlock_version`): `_human` (INV-1, as the reveal: a live person in a
  request, not support, not a client) → `visible_version` (404/403) → `authorise(evidence.unlock)`
  on the engagement → not a PDF, already derived or not encrypted → 409
  `not_password_protected`. One unit of work: a per-(person, version) advisory lock, count
  `evidence_version.unlock_failed` audit rows by this person on this version in 15 minutes
  (kernel helper `audit_actor_count_since`); 5 → 429 `unlock_rate_limited` with `retry_after`.
  Run the child (`asyncio.to_thread(run_isolated, …)`). Wrong → audit `unlock_failed` (attempt
  count only) and `{wrong_password, attempts_left}`. Unlocked → store each word page and PNG
  (sealed, content addressed), insert the derivation, `evidence_pages`, `pii_scan_runs`,
  `pii_regions` (values sealed), `upload_previews` + pages, all with `derivation_id`; audit
  `evidence_version.unlocked` and emit the outbox event `EvidenceVersionUnlocked`.
- **Readers** (`repository`): `pages_of`, `pii_regions_of`, `scanned_pages`, `unscannable_pages`,
  `scan_run_for`, `masked_preview_for` take `derivation_id` (default None: unchanged behaviour,
  every existing caller still reads only non-derived rows); `insert_derivation`,
  `current_derivation`. `projection_of` and `masked_text.masked_pages` pass it through.
- **Viewer**: the manifest, pages, text and search of a version with a derivation read the
  derivation's records; the manifest carries `derivation_id`, and `allowed_actions` offers
  `evidence.unlock` on a `password_protected` version when the flag is on and the person holds it.
- **Reveal**: a region of the version's current derivation may be revealed (same rules).
- **Route**: `_gate(EVIDENCE_VIEWER_UNLOCK)`, errors 409 and 429; `make generate`.
- **Synthetic**: `abacus_tools.synthetic.documents.password_pdf(password)` — a real RC4 (R2)
  standard-security PDF (no dependency) holding the Halvard consolidated 1099 with a 9xx TIN.
- **Not done here**: a derived `upload_extractions` row (agent material and `upload.check`
  re-run for an unlocked file, OQ-8). Agents keep reading the original's material, which an
  encrypted file never has, so nothing unmasked reaches them (DEC-425).
- No migration: 0109 created the tables, columns and grants. Reserved 0173–0174 unused.

## Tests
`backend/tests/integration/evidence/test_unlock_derivation.py` (`test_ac5_…`): right password →
ready, derived masked pages linked to the untouched version (bytes and fingerprint unchanged),
manifest `ready` with `derivation_id`; wrong → `attempts_left`, audited by count; 6th → 429; not
locked → 409; agent/system/client refused; sentinel password absent from logs, audit rows,
derived tables and storage objects. Unit: `password_pdf` opens with the password only.

## Rollback
Flag `evidence.viewer_unlock` off (routes 404). Derived rows are additive; readers default to
non-derived rows.

## Progress log
- 2026-10-26: plan written; built. Targeted pass (one run, `-n 2`): the unlock unit and
  integration files, the trust-kit PII scan, reveal, viewer, masked-rendition, offshore-material
  and word-layer files, the C4 contract tests, route introspection and the T18 independent suite:
  778 passed. Gates clean (ruff, pyright, lint-imports, banned_patterns, error_codes --write,
  validate_docs, scope_guards, fresh_mfa, secrets_scan, check-generated). No migration needed
  (0109 has the tables and grants); 0173-0174 unused. Follow-ups: a derived extraction for agent
  material and the OQ-8 check re-run; human-only audit listing for `evidence_version.unlocked`
  would need a migration.
- 2026-10-26: security review (PASS) fix round. M1: the TASK-323 upload unlock route shares the
  guard (`unlock._attempt`) and refuses non-request callers; declares 429. M2: no core dumps in
  the isolated child. L1: migration 0173 (`down_revision` 0172, re-point at merge), one unlock per
  version, the loser 409. L2 and L3 recorded as follow-ups in DEC-425. Tests:
  `tests/integration/test_p03t19_unlock_hardening.py` (4), `tests/unit/kernel/test_isolation_no_core.py`.
