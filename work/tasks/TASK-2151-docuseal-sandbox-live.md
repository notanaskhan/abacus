---
id: TASK-2151
title: DocuSeal sandbox run - N-02-T06 findings and the T18 adapter fixes they force (ADR-342)
spec: SPEC-381
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T06
branch: n02-docuseal-live
created: 2026-10-30
updated: 2026-10-30
---

## Objective

The DocuSeal developer sandbox account exists (F-09-T08, sandbox half). Run the merged adapter
(N-02-T18, #814; status #815) against the real API, settle every `[verify]` item it carried, and
answer N-02-T06's spike questions from the sandbox rather than the docs. Fix what the run shows
is wrong. The API key lives outside git (the builder's macOS Keychain for local runs; the vault
copy and each firm's sealed install are human steps). No key, account ID, price or person appears
here.

## Plan

- `signatures/docuseal.py`: `DOCUMENT_HOSTS` narrowed to the one host the sandbox served; field
  `title`s for the signer (our field names stay internal); date fields read-only with DocuSeal's
  signing-date default; submitter `name` dropped; signer IP and device read from the audit log
  text (`audit_entries`, a new `audit_text` dependency), and a completed signer with no IP there
  refused (`DocuSealError("audit_log")`) so evidence is never written without one; KBA comments
  corrected to DocuSeal's step order.
- `signatures/docuseal_firm.py`: `audit_log_text` reads the audit log PDF in the isolated child
  (ADR-110), as `page_sizes` does; passed as `audit_text`.
- Tests: `tests/unit/signatures/test_n02t18_docuseal_adapter.py` follows the sandbox shapes
  (empty event data); new tests for titles and the read-only signing date, the audit-log parse,
  and the refusal without an IP. No test weakened: the IP assertion stays, from its real source.
- Docs: DEC-1278; N-02-T06 and F-09-T08 rows to `partial`.
- No migration, flag, capability or registry change. Rollback: revert the commit; nothing stored
  changes shape (`SignerEvidence` is the same dataclass).

## Findings (sandbox, 2026-10-30)

Recorded in DEC-1278. In short:

1. Create, idempotent re-create (same submission back), status, merged document, audit log,
   signature image and archive all work as built. Fields as page fractions from the top-left land
   where placed (checked on the rendered signed PDF).
2. File URLs (signed PDF, audit log, signature image) are all `https://docuseal.com/file/…`: 200,
   no redirect, no key. The API's `combined_document_url` stays null; `documents?merge=true`
   works.
3. `submission_events[].data` is empty (`start_form`, `view_form`, `complete_form`,
   `api_complete_form`); `ip`/`ua` exist only in webhook payloads. The audit log PDF carries each
   signer's IP, session ID, user agent and time zone, and both document SHA-256s.
4. The signing page sends `X-Frame-Options: SAMEORIGIN`: no iframe. Same-tab redirect is the
   only presentation (DF-12). `completed_redirect_url` per submitter returns the signer after
   completion (verified). The link stays valid after completion and offers Download and "Send
   copy via email": the slug is a bearer link to the signed document.
5. Field names are shown to signers unless a `title` is given; the submitter `name` is pre-filled
   into a typed signature; a `date` field is signer-entered unless read-only with `{{date}}`.
6. The `kba` field type is accepted. DocuSeal asks KBA as the form's last step (after signature
   and date): first name, last name, address, city, state, ZIP, phone, email, date of birth and
   SSN, then the verification. Not run (it is a paid check on real identity data). Failure and
   lockout reporting stays `[verify]` until F-09-T63.
7. The signing page loads a third-party analytics script (DocuSeal's own, cookieless) besides its
   own: a note for the sub-processor register.

## Progress log

- 2026-10-30: key verified (US API host 200, EU 401). Ran the adapter as merged: create, retry,
  status; completed signers through the API (no image, no IP) and in the browser (real evidence).
  Probed titles, read-only signing date, redirect, no-name. KBA form viewed, not submitted; KBA
  submission archived. Fixes built; unit file 12 passed; adapter re-run end to end on the sandbox
  with a browser-signed submission: evidence complete (IP, Chrome · macOS, image, audit log).
