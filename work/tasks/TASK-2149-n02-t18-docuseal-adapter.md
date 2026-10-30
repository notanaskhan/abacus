---
id: TASK-2149
title: N-02-T18 rework - DocuSeal adapter behind the EsignProvider port (W7; ADR-342)
spec: SPEC-381
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T18
branch: n02-t18-docuseal
created: 2026-10-30
updated: 2026-10-30
---

## Objective

ADR-342 (accepted 2026-10-30) replaces DocuSign with DocuSeal's hosted API. This reworks
N-02-T18 (#775, TASK-2139) against the re-scoped row. Acceptance (backlog row): "Against the
DocuSeal sandbox a two-signer envelope is created exactly once under a retried send and its
request and response evidence is stored write-once." The sandbox run is a human to-do (no
account yet); the same behaviour is proven here against a recorded DocuSeal transport.

## Plan

- `signatures/docuseal.py` (new, replaces `docusign.py`):
  - `X-Auth-Token` API key from the sealed install secret (`{"api_key", "api_host"}`); only
    `api.docuseal.com` is allowed (the EU host stays refused until data location is decided).
    Document, audit-log and signature-image URLs are fetched only from DocuSeal's file hosts
    (`DOCUMENT_HOSTS` [verify on the sandbox]); anything else is refused before a request.
  - `create_and_send`: `POST /submissions/pdf` with base64 PDFs, one role per signer
    ("Signer n"), fields as `areas` in page fractions (PDF points over the page size; top-left
    origin as SIG-02 places them), a `kba` field before the signature for the e-file family,
    `send_email: false` and `send_sms: false` everywhere, submitter `order` (sequential: rank;
    parallel: routing group), `external_id` = our signer id and `metadata.accrued_idempotency`.
    Exactly once: `GET /submitters?external_id=<first signer>` first; a submitter carrying the
    same idempotency key is read back instead of creating again.
  - Anchored fields are refused (DocuSeal has no anchor search; P-11's rendered letters will
    carry DocuSeal text tags instead). Generated documents stay refused as before.
  - `status`: `GET /submissions/{id}`; awaiting/sent → pending, opened → viewed, completed →
    signed, declined → declined. KBA failure reporting is unknown until N-02-T06 [verify].
  - `completed`: `GET /submissions/{id}/documents?merge=true` (combined PDF), the submission's
    `audit_log_url` (the certificate), each completed submitter's signature image from its
    values; IP and user agent from the submitter's `complete_form` event data [verify].
  - `remind`: confirms the submitter exists and sends nothing (reminders are Accrued mail,
    `reminder_sender`; ADR-342). `void`: `DELETE /submissions/{id}` (archive).
- `signatures/docuseal_firm.py` (replaces `docusign_firm.py`): flag `signatures.esign_provider`,
  `register_esign_install`, page sizes read in an isolated child (`run_isolated`, pypdfium2;
  envelope documents are client files, ADR-110), field `w`/`h` now loaded.
- `integrations/secrets.py`: `esign_install_secret`, catalogue key `docuseal`; `api.py` export;
  worker wiring.
- `write-capabilities.yaml` W7 `adapter_key: docuseal`, decision ADR-342; regenerate
  `_capabilities.py`.
- Flag: `signatures.docusign` → `signatures.esign_provider` in `feature-flags/signatures.yaml`;
  regenerate `kernel/_flags.py`.
- Migration 0406 (expand-only): `envelopes.provider` CHECK adds `docuseal`, keeps `docusign`
  (a later contract step removes it once no row can hold it).
- `contract.py` `Provider` adds `docuseal`; `make generate` for the API client.
- `builder.DRAFT_PROVIDER = "docuseal"`; `status_poll` reads the new flag and `docuseal` rows
  (its Connect helpers stay until the N-02-T19 rework).
- `banned_patterns`: the AUTH excludes move from `docusign.py` to `docuseal.py`.
- Tests: `tests/unit/signatures/test_n02t18_docuseal_adapter.py` (recorded transport) replaces
  the DocuSign one; integration expectations that named `docusign` as the draft provider move.
- Rollback: revert the PR; 0406's downgrade restores the old CHECK (no `docuseal` rows exist
  while W7 is closed).

## Human to-dos

- W7 stays declared and disabled (ADR-150 v2 opens it).
- DocuSeal sandbox account; install row with sealed secret `{"api_key", "api_host"}`; run the
  acceptance against the sandbox and confirm `DOCUMENT_HOSTS`, the KBA field behaviour and the
  `complete_form` event data.
- Q-01's egress firewall lists `docuseal.ALLOWED_HOSTS` and `DOCUMENT_HOSTS` when W7 opens.

## Progress log

- 2026-10-30: plan written from DocuSeal's OpenAPI spec (`console.docuseal.com/openapi.yml`).
- 2026-10-30: built. Adapter unit tests 9 pass (12 in `tests/unit/signatures`; self-review added: only a 2xx is accepted, so a redirect body is never stored); signatures,
  schema-check and schedules integration 294 pass (0406 applies and reverses); contract suites
  5,574 pass; integrations integration 34 pass; ruff, pyright (whole tree), lint-imports,
  banned_patterns, validate_docs, scope_guards, secrets_scan and the generated-file checks clean;
  web `tsc` clean after `make generate`. Unit suite: 23 failures, identical on the base commit
  27e096eff (main's tax `WORKFLOWS`, DEC-836, methodology actor-kind, audit targets), none from
  this change.
