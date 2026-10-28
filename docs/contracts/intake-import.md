# Intake and import · CLI-06 (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` |
| Version | v1 |
| Status | live for dedupe, intake drafts and commit (P-07-T42, 2026-10-26) and for imports (P-07-T52, 2026-10-27) |
| Provider epic | P-07 (`engagements`, the intake and import package; dedupe reads `organisations` through its api) |
| Consumers | CLI-06 single intake (P-07-T49) and bulk import (P-07-T54); the consumer suite P-07-T45; the implementations P-07-T42 (dedupe, drafts, commit) and P-07-T52 (imports) |
| Freeze sprint | the sprint review after the stub (P-07 §8.1) |
| Flag | `clients.v2` (CLI-06's flag; default off) |
| Spec | `docs/specs/SPEC-332-acceptance-independence-conflicts-in-app.md` (AC-23 to AC-26 for the conflict step); P-07 §3.3 Stories 3.1 and 3.2, §4.2 M8 and M9, §4.3 |
| ADRs | ADR-005, ADR-026, ADR-031, ADR-052, ADR-139 (P-36); DEC-43, DEC-52, DEC-62, DEC-143 (OQ-2), DEC-326, DEC-373, DEC-374 |

## 1. Purpose
CLI-06 adds a client, or an entity under an existing client, in one unit of work, and imports a practice-management client list once with a person deciding every uncertain row. Consumers can rely on: a dedupe read with scored candidates; an autosaved, owner-only intake draft per wizard step with per-step validation; a commit that creates the client or entity, relationships, contacts, Prospect engagements with their work items, links the conflict check and optionally opens an acceptance record, replayable by `Idempotency-Key`; a bulk import with counts, rows (masked TINs), row decisions and an asynchronous run, replayable by `Idempotency-Key`.

**Behaviour.** Every route refuses a client principal, an agent and the system (403), authorises its action firm-level, and only then reads `clients.v2`: off, 404. Dedupe, the intake drafts and the commit are live (P-07-T42, DEC-430, DEC-441); the imports are live (P-07-T52, DEC-643). Commit and run require the `Idempotency-Key` header (422 without it, before anything else answers).

**Live intake (P-07-T42).** Dedupe scores per DEC-441 (same normalised name 1.0; the same name less fiduciary designators 1.0 − 0.02 per word, so "Estate of Walter Thornbury" → "Walter Thornbury" is 0.96; else trigram similarity ≥ 0.6). Drafts are the person's own; an SSN or ITIN form in the draft's text on a firm that is not synthetic is 422 `tin_kind_not_allowed` before anything is stored (OQ-4). Validation reports `(field, code)` problems per step, `date_of_death_required` on `entity.date_of_death` when Form 706 is a service, and `gate_unmet` on the conflicts step until the draft's own conflict check (subject `client_intake_draft`) is clear for the person. A check on an intake draft searches the names the server builds from the draft (the request's `names` are not searched; a draft with none is 422 `invalid`), and the commit requires that those names still equal the draft's and re-reads the outcome in its unit of work; a name changed after clearance needs a new check (security review H1, DEC-430). The commit (its draft then final: payload emptied, `result` kept, further updates refused by a trigger) writes, in one unit of work, the client (status `prospect`) or a new entity under an existing client, the entity's type and date of death, relationships from the new entity, contacts with roles on the new entity, one Prospect engagement per engagement type and period with the engagement partner and its work items (`form_56` creates none), and with `start_acceptance` an acceptance record per engagement; a committed draft answers its stored result again.

**Live import (P-07-T52, DEC-643).** The upload (CSV, UTF-8, at most 5 MB and 2,000 rows) is mapped by its headings (the CCH Axcess Tax client-list headings or plain synonyms; `mapping` names each column's field), every cell kept as inert text (bidi and control characters removed, TIN forms in names scrubbed), and every row scored against the clients the person may see: an entity holding the row's EIN (by fingerprint) is 1.0 on basis `ein`, else the dedupe's best candidate. At or above 0.9 a row is `merge`; with no candidate it is `new`; otherwise it waits for a person. On a firm that is not synthetic an SSN or ITIN is dropped, never stored, and the row carries `tin_kind_not_allowed`. The import lands in `reviewing`; the file is kept sealed for 30 days, then erased. A decision is `new`, `merge` (into the match, or `merge_client_id`, a client the person may see), `keep_both` (needs a match) or `skip`. Run (202) starts `ClientImportWorkflow`: undecided rows are skipped, each other row is applied once as the system acting for the person who ran it (their walls apply), `new` and `keep_both` create the client, entity and contact, `merge` adds the row's contact when its email is new to the client and never changes a TIN; a row that fails keeps its `error_code` and the rest carry on. The import then reads `done` with `imported`, `skipped`, `new` and `failed` counts; a second run is 409 `import_already_run` (the person who ran it may call run again while it is `importing`, which starts nothing twice).

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/organisations.yaml`. Every route is one action.

| Operation | Method and path | Matrix action | Roles allowed | Agent or system |
|---|---|---|---|---|
| Dedupe | `POST /v1/clients/dedupe` `{name, kind?}` | `client.create` (new) | firm admin, partner (`firm_partner`), manager (`firm_manager`) | denied |
| Intake drafts | `POST /v1/client-intake-drafts` · `GET`/`PATCH`/`DELETE …/{draft_id}` · `POST …/{draft_id}/validate` | `client.intake` | firm admin, partner, manager (derived cells) | **denied** |
| Commit | `POST …/{draft_id}/commit` `{start_acceptance}` + `Idempotency-Key` | `client.intake` | as above | **denied** (human-only) |
| Upload an import | `POST /v1/client-imports?source=&filename=` (the file is the raw body) | `client_import.run` (new) | firm admin, partner, manager | **denied** |
| Read an import, its rows | `GET /v1/client-imports/{import_id}` · `GET …/{import_id}/rows?cursor=&limit=&review=` | `client_import.run` | as above | denied |
| Decide a row | `PUT …/{import_id}/rows/{row_id}/decision` `{decision, merge_client_id?}` | `client_import.run` | as above | **denied** |
| Run | `POST …/{import_id}/run` + `Idempotency-Key` → 202 | `client_import.run` | as above | **denied** |

No client role holds any action here. A walled client is never a dedupe candidate, never a merge target and answers 404 (DEC-43).

## 3. Models
Code: `backend/src/abacus/modules/engagements/intake_contract.py`. Every field carries a classification tag.

- **Dedupe:** `DedupeIn` (`name` confidential, in the body; `kind` the client kind; no TIN digits: an EIN match comes from stored fingerprints), `DedupeOut` (`candidates` `DedupeCandidateOut`: `client_id`, `display_name`, `client_entity_id`, `entity_name`, `score` 0–1, `basis` name · ein).
- **Intake drafts:** `ClientIntakeDraftPayload` (identifiers and typed values only, no TIN: `entity` `IntakeEntityIn` with `mode` new_client · existing_client, `client_id`, `client_display_name`, `entity_name`, `entity_type`, `date_of_death`; `relationships` `IntakeRelationshipIn`; `contacts` `IntakeContactIn` with `roles`; `services` `IntakeServiceIn` with an ENG-03 catalogue `type_code` (or `form_56`, a line item), `forms` (the type's forms to create; default all, P-07-T42) and the period; `engagement_partner_user_id`; `conflict_check_id`), `ClientIntakeDraftIn` (`step` entity · relationships · contacts · services · conflicts · review), `ClientIntakeDraftPatchIn` (`seen_version`), `ClientIntakeDraftOut`, `ClientIntakeDraftDiscardedOut`, `IntakeValidateIn`, `IntakeValidationOut` (`problems` `IntakeProblemOut` field and code, e.g. `date_of_death_required`).
- **Commit:** `IntakeCommitIn` (`start_acceptance`), `IntakeCommittedOut` (`client_id`, `client_entity_id`, `engagement_ids`, `engagement_status` C2 `engagement` = prospect, `work_item_ids`, `conflict_check_id`, `acceptance_record_id`).
- **Imports:** `ClientImportOut` (`source` cch_axcess_tax_export · csv; `stage` uploaded · mapped · reviewing · importing · done · failed, a code whose words are CLI-06's (P-07-T54, DEC-812); `file_name`; `mapping` column → field code; `counts` `ClientImportCountsOut` with `rows`, `matched`, `to_review`, `new`, `skipped`, `imported`, `failed`), `ClientImportRowsOut` (the list envelope's `items`, `next_cursor`, `total`), `ClientImportRowOut` (`row_no`, `display_name`, `entity_type`, `tin` organisations' `MaskedTinOut` (kind, presence, last four; restricted), masked further for an offshore reader; `best_match_client_id`, `best_match_name`, `score`, `decision` new · merge · keep_both · skip, `decided_by`, `error_code`), `RowDecisionIn`.

No model carries a plain TIN, a hidden-by-wall field or a count of walled clients.

## 4. Status words
C2 `engagement` (`prospect`) on commit. The import's `stage` and a row's `decision` are codes, not registry statuses; CLI-06's `copy.ts` words them (P-07-T54, DEC-812).

## 5. Human-only actions
`client.intake` (and so the commit) and `client_import.run` deny `agent` and `system` at the matrix; the live services (P-07-T42, T52) also require a live human. A row below the auto-match threshold (90%) is never merged without a person's decision.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 403 | `{"detail": "forbidden"}` | a client principal, an agent or the system; a role without the action |
| 404 | `{"detail": "not found"}` | `clients.v2` off; another person's draft; a walled or unknown client, draft or import |
| 422 | validation | a missing `Idempotency-Key` on commit or run; more than the bounds |
| 409 | `stale_version` · `possible_duplicate` · `entity_exists` · `gate_unmet` (`gate: conflict_check`) · `acceptance_template_missing` | commit and autosave (P-07-T42). A commit that loses a race with another commit of the same draft answers the winner's stored result (as a later commit does) or `stale_version` when the draft is not committed, never 500 (ED-116, DEC-461) |
| 422 | `draft_incomplete` (`facts.step`) · `tin_kind_not_allowed` · `idempotency_key_reused` · `invalid` (`field: engagement_partner_user_id`) | commit; create and autosave for the TIN guard (P-07-T42) |
| 409 | `import_already_run` | a decision or a second run after the run (P-07-T52) |
| 422 | `import_row_invalid` (`facts.field`) | a row decision the row does not allow: `merge` with nothing to merge into, `merge_client_id` with another decision, `keep_both` without a match (P-07-T52) |
| 422 | `import_file_invalid` (`facts.reason`: `empty_file`, `file_too_large`, `not_utf8_csv`, `not_cch_export`, `no_name_column`, `no_rows`, `too_many_rows`) | an upload the import can't read (P-07-T52, additive) |

## 7. Audit and outbox events
Live (P-07-T42): `client_intake.started`, `client_intake.saved` (version only), `client_intake.discarded` on the draft; `client_intake.committed` on the client (with `client.created` or `client_entity.created`, `relationship.created`, `contact.created`, `engagement.created`, and with acceptance `acceptance.record_opened`), `client_import.uploaded` (source, rows, to review), `client_import.row_decided` (row number, decision), `client_import.started` (the run), `client_import.row_applied` per row the run applied, `client_import.completed` or `client_import.failed` (the counts), `client_import.files_erased` (the daily erase, a count; P-07-T52). Outbox: `client.created`, `client_entity.created`, `engagement.created`, `client_import.completed` (identifiers only).

## 8. Example payloads
Brightwater Hale, synthetic; ids are placeholders.

`POST /v1/clients/dedupe` `{"name": "Estate of Walter Thornbury", "kind": "trust_family"}` → `{"candidates": [{"client_id": "…", "display_name": "Walter Thornbury", "score": 0.96, "basis": "name"}]}` (CLI-06 b "96% match · Walter Thornbury").

`GET /v1/client-imports/{id}` (CLI-06 g) → `{"stage": "reviewing", "counts": {"rows": 212, "matched": 204, "to_review": 8, "new": 0, …}, …}`.

## 9. Consumer contract tests
- Stub: `backend/tests/contracts/intake_import/test_intake_import_stub.py`.
- Consumers (P-07-T45): `backend/tests/contracts/intake_import/test_intake_import_consumer.py`, the CLI-06 g tallies 204, 8 and 0 and the masked TIN shape in import rows.
- Independent AC suite (P-07-T44): `backend/tests/integration/backfill/test_p07t44_intake_commit_independent.py`.

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | stub 2026-10-26 (P-07-T37); intake live and `IntakeServiceIn.forms` added (additive) 2026-10-26 (P-07-T42); imports live, 501 retired and `import_file_invalid` added (additive) 2026-10-27 (P-07-T52) |

## 11. Open points
- DEC-430, DEC-441: the live intake's choices and the dedupe score (P-07-T42).
- DEC-643: the live import's choices (the sealed file and its 30-day erase, heading mapping, undecided rows skipped, merge never writing a TIN; P-07-T52). CLI-06 shows the heading map read-only; no mapping route in v1 (P-07-T54, DEC-812).
- DEC-374: the stub's choices (the raw-body upload instead of multipart, `client.create` as a new action, no new flag, the masked row TIN (`MaskedTinOut`) through `mask_tins_for`, no EIN digits on dedupe, intake in `engagements`).
