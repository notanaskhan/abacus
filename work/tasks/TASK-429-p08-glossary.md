---
id: TASK-429
title: Glossary rows for P-08 - portal_branding, portal_domain, portal_preferences, sign_in_challenge, trusted_device, mfa_backup_code, secure_link; UI terms Client portal, Sign-in code, Two-step verification; portal copy bans (P-08-T04)
spec: SPEC-046
acceptance_criteria: [AC-13]
risk_zone: red
status: done
epic: P-08
plan_key: P-08-T04
branch: TASK-429-p08-glossary
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The glossary PR merges and banned_patterns accepts the new identifiers." Add the protected
glossary rows P-08's migrations and screens need before they land (P-08 §4.2, §4.9, §5.7), so
P-08-T05, T10, T17 and T21 name their tables from the glossary, and record the portal copy bans.
Solo edition: decided and recorded by the builder (AMENDMENT-solo §2).

## Plan (red zone: docs only)
- Files: `docs/product/glossary.md`; `backend/tests/unit/quality/test_glossary_l12.py`.
- No migration, registry, flag or matrix edit. No new "Don't use" entries, so the L12 identifier
  ban list is unchanged and no existing identifier can start failing (`password` appears in tooling
  and fakes, so it is a copy ban, not an identifier ban).
- Tests: the new code names and UI terms are glossary rows; L12 passes the seven tables and their
  classes; `link` stays banned outside the `secure_link` compound.
- Rollback: revert the commit.

## What changed
- **New terms: identity** `Sign-in challenge` (`sign_in_challenges`; UI "Sign-in code" for the
  code; 10-minute code, 3 wrong codes → 15-minute lock, DEC-35), `Trusted device`
  (`trusted_devices`, 30 days or fewer), `MFA backup code` (`mfa_backup_codes`, 8 single-use, shown
  once, DF-17), `Two-step verification` (UI term for portal MFA, DEC-34 floor).
- **New terms: communications** `Secure link` (`secure_links`, single-use, 14 days, renewal only to
  the original address, token in the fragment; `link` stays banned on its own).
- **New terms: portal** (new section) `Client portal` (UI term; code `portal`; never "Accrued",
  ADR-163), `Portal branding` (`portal_branding`, slots only, footer off by default),
  `Portal domain` (`portal_domains`, default or custom host, branding hint only), `Portal
  preferences` (`portal_preferences`, per scope, welcome dismissed).
- **Copy-level bans** "password", "task" or "Accrued" in portal copy, sign-in and invitation
  emails or portal error messages → "Sign-in code" / "Two-step verification", "to-do", the firm's
  name (L2, L7).
- **Tests** three P-08 cases in `test_glossary_l12.py`.

## Collision check
`glossary_bans()` holds `link` (→ `fulfilment`) and `task` (→ `request_item`) but none of the new
table names or their first words (`portal`, `sign`, `trusted`, `mfa`, `secure`). L12 compares whole
names, singulars and table first words, so `secure_links` passes while `Link` alone fails (tested).

## Progress log
- 2026-10-23: rows written from P-08 §0.1, §3.2–3.5, §4.2, §5.7, DEC-34, DEC-35, DF-17 and
  ADR-163. Checks: `pytest tests/unit/quality/test_glossary_l12.py test_glossary_report.py`
  (16 passed), ruff, `banned_patterns`, `glossary_report` (193 terms, 106 bans),
  `make check-generated`, `validate_docs`.
