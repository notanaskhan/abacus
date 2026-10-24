# C4 · Citation v2, viewer manifest, regions, masked PII and logged reveal (v1)

| Field | Value |
|---|---|
| Register row | C4 in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub. This doc is P-03-T01 (2026-10-23); the models, fixture routes, matrix rows and flags are P-03-T02 |
| Provider epic | P-03 (`evidence`) |
| Consumers | SHL-07 and SHL-08 (P-03-T07, T11, T14, T20); F-05 L2 shells (F-05-T41, T44, T47); P-04 (SHL-09/10, `uncited_change`, Cite selection); P-06 and A-01 (SHL-20, AUD-03); A-02 (AUD-06 dock viewer); N-01 (FIL-01); K-01 (`methodology_step`); P-11 (word layer); T-01 (the reveal pattern); P-09 and P-10 (CiteMarkers, number provenance); F-04 (INV-2 checker) |
| Freeze sprint | S5 (starts 2026-12-28) |
| Flags | `evidence.citations_v2`, `evidence.viewer_v1`, `evidence.pii_reveal`, `evidence.viewer_unlock`. ADR-089 booleans, per firm, default off, rollout only (DEC-55); the owner and expiry are set in the stub PR. Masking is never behind a flag |
| Spec | `docs/specs/SPEC-322-trust-kit-v1.md` |
| ADRs | ADR-166 (P-48; the plan's alias "ADR-144"), ADR-066, ADR-004, ADR-110, ADR-005, ADR-031, ADR-052, ADR-104, ADR-139 (P-36), ADR-140 (P-39), ADR-145 (P-06); DEC-16, DEC-43, DEC-52, DEC-55, DEC-60, DEC-147, DEC-148 |

Shapes follow `docs/plan/epics/P-03.md` §4.3 and §8.1 exactly. Where this doc gives less detail than §4.3, the epic's shape governs; those places say "shapes per P-03 §4.3".

## 1. Purpose
Consumers can rely on the following:
- Every citation is an insert-only, code-verified row of one of ten kinds (ADR-166). Its display (`title`, `loc`, `quote`) is rendered by the server, and its state (`valid`, `moved`, `broken`, `relinked`) is computed.
- Every page image is a server-rendered, masked PNG. The viewer manifest carries geometry and mask tokens, never text.
- A masked value is revealed only by a live, onshore person, and the reveal is logged.
- A password PDF is unlocked into derived records without changing the evidence.

Walls answer 404, with no hidden count anywhere (DEC-43, INV-3). Client principals hold no C4 action (INV-4).

**Stub behaviour (P-03-T02).** Each route answers only when its flag is on (§2). Until its implementing task lands, it returns seed-derived Brightwater Hale fixtures. With its flag off, a route is absent (404), the repo's stub convention (as in `clients.md`). `POST /v1/citations` is reserved and answers 501 until its first anchor consumer (P-04).

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/evidence.yaml` (evidence section, F-03-T07). Every route is under `/v1`, declares exactly one matrix action, applies `authorise` and then `visible()` (ADR-145 scope kinds; engagement-scoped only until ADR-158 lands with N-01-T06), uses the P-36 list envelope and error facts, and answers 404 for walled or invisible resources.

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal | Flag |
|---|---|---|---|---|---|
| Citation display | `GET /v1/citations/{citation_id}` | `citation.read` (new) | engagement_partner, manager, senior, staff, reviewer, eqr_reviewer allow; practice_leader and quality_partner `in_scope`; `independence: required`. `client_service`, client roles and platform support are denied | agent `task_scope` | `evidence.citations_v2` |
| Citation lists | `GET /v1/citations?anchor_type=&anchor_id=&anchor_ref=` (anchor stack, ordered by `n`) · `?host_ref=&section_id=` ("Citations (n)", "Procedures (n)") · `?source_version_id=` (linked-figure rows, auto-highlight) · `&kind=` | `citation.read` | as above | agent `task_scope` | `evidence.citations_v2` |
| Re-link | `POST /v1/citations/{citation_id}/relink` | `citation.relink` (new) | engagement_partner, manager, senior, staff; `independence: required` | **denied** | `evidence.citations_v2` |
| Cite selection (**reserved**) | `POST /v1/citations` | `citation.create` (new, reserved) | engagement_partner, manager, senior, staff; `independence: required` | **denied** | `evidence.citations_v2`; answers **501** |
| Viewer manifest | `GET /v1/evidence-versions/{version_id}/viewer` | `evidence.read` | unchanged | unchanged | `evidence.viewer_v1` |
| Masked page | `GET /v1/evidence-versions/{version_id}/pages/{page_no}` | `evidence.read` | unchanged | unchanged | `evidence.viewer_v1` |
| Regions | `GET /v1/evidence-versions/{version_id}/regions?match_ids=` | `evidence.read` | unchanged | unchanged | `evidence.viewer_v1` |
| In-document search | `GET /v1/evidence-versions/{version_id}/search?q=` | `evidence.read` | unchanged | unchanged | `evidence.viewer_v1` |
| Reveal a masked value | `POST /v1/evidence-versions/{version_id}/pii-reveals` | `pii.reveal` (new) | engagement_partner, manager, senior, staff, eqr_reviewer; `not_offshore`, `independence: required`, `mfa_recent: required` for TIN kinds. Client roles, `client_service` and platform support are denied | **denied** (agent and system) | `evidence.pii_reveal` (also the reveal kill switch, ADR-097) |
| Unlock a password PDF | `POST /v1/evidence-versions/{version_id}/unlock` | `evidence.unlock` (new) | engagement_partner, manager, senior, staff; `independence: required`. Client roles are denied | **denied** | `evidence.viewer_unlock` |
| Download (exists, unchanged) | `GET /v1/engagements/{id}/evidence-versions/{vid}/content` | `evidence.read` | unchanged | unchanged | none |

The existing page routes `…/request-items/{item}/uploads/{version}/preview/pages/{n}` (`evidence.read`) and `…/inbox/{file}/preview/pages/{n}` (`evidence.upload`) keep their paths and actions. They delegate to the same masked source.

## 3. Models
The code lands with P-03-T02 under `backend/src/abacus/modules/evidence/` (shapes per P-03 §4.3 and §8.1). The names below are the plan's (§8.1). Where the stub's Python class names differ (for example `CitationV2Out`, `ViewerManifestOut`, `EvidenceUnlockOut`), the stub's names are the code names and the shapes are the same. Tags: **R** restricted, **C** confidential, **I** internal (ADR-031).

### 3.1 `CitationV2`: a discriminated union on `kind`
Each kind has a locator (chapter 05 §5.3.10) and a `match_id` derived by the server. The client never sends a `match_id`.

| `kind` | Locator fields | `match_id` |
|---|---|---|
| `document_text` | `evidence_version_id` (or `inbox_file_id` for a file still in the inbox, the matcher's; DEC-267), `page`, `bbox?` `[x0, top, x1, bottom]`, `annotation_id?` (**reserved**, always null in v1; K-03) | `ev:<version>#p<page>:<x0>,<top>,<x1>,<bottom>` (`inbox:<file>#p…` for an inbox file) |
| `sheet_cell` | `evidence_version_id` (or `inbox_file_id`; DEC-267), `sheet`, `cell`, `value?` | `<file>!<cell>` (`inbox:<file>!<cell>`) |
| `ledger_line` | `ledger_snapshot_id`, `account_code`, `period`, `amount`, `txn_id?` | `led:<snapshot>:<account>` |
| `workpaper_cell` | `sheet_id`, `row_key`, `column_key`, `sheet_version` | `wp:<sheet>.<row>.<col>` |
| `methodology_step` | `template_version_id`, `step_key`, `step_n` | `ms:<step_key>@<ver>` |
| `policy_rule` | `threshold_policy_id`, `version`, `rule_key` | `pol:<id>@v<n>` |
| `record_field` | `record_type`, `record_id`, `field`, `as_of_version` | `rec:<type>:<id>.<field>` |
| `tax_form_line` | `return_id`, `year`, `form`, `line`, `value` | `tax:<return>:<form>:<line>` |
| `artifact_cell` | `run_artifact_id`, `sheet`, `cell` | `art:<id>!<cell>` |
| `request_item` | `request_item_id` | `req:<id>` |

All locator ids are I. `value` and `amount` are C.

### 3.2 `CitationDisplay` (`GET /v1/citations/{id}`; list items)
- **Identity and kind:** `id` I, `n` I, `kind` I.
- **Rendered by code from the locator,** never from model text: `title` C, `loc` C.
- **Quote:** `quote` R. It is re-read from the masked word layer, or null. `quote_state` I is one of `shown`, `withheld` or `changed`; it compares the re-read text with `quote_sha256`.
- **Values:** `value_text` C, `match_id` I.
- **State:** `state` I is one of `valid`, `moved`, `broken` or `relinked` (the C4 stub's codes), computed from `citation_events`. `verified` I. `verification_reason` I is null or one of `page_not_found`, `cell_not_found`, `quote_not_found`, `value_mismatch`, `bbox_mismatch`, `source_not_found`, `source_not_visible` or `locator_invalid`.
- **Provenance:** `created_by` I is `{kind, label}`. `kind` is `agent`, `human` or `system`, and the label reads "‹person› via Agent" for agent rows. `retrieved_at` I.
- **Source:** `source` I is `{type, id, version, evidence_version_id?, page?}`.
- **Use and actions:** `used_in` I is a count, null when the lineage cut is invoked. `moved?` C is the successor reference and date the "Source moved — …" line is built from. `allowed_actions` I may include `citation.relink`.

No field carries the stored hash, a quote the client sent, or a hidden-by-wall count. List responses are `ListPage[CitationDisplay]`.

### 3.3 `ViewerManifest` (`GET …/viewer`)
- **File:** `evidence_version_id` I, `file_name` C, `media_type` I.
- **Status:** `status` I is one of `processing`, `ready`, `password_protected`, `unreadable` or `not_previewable`. `reason` I. `kind` I is one of `pages`, `image`, `table` or `none`. `page_count` I, `truncated` I.
- **Pages:** `pages[]` holds `{n, width_pt, height_pt, rotation, image_w, image_h, text_layer, pii_scan: done | not_scannable}`, all I.
- **Masks:** `pii_masks[]` holds `{id, page, rect, kind, display}`. `display` is the mask token, for example `•••-••-6081`. The `display` field is C; the others are I.
- **Other:** `derivation?` I (the unlock derivation id), `allowed_actions` I (`pii.reveal`, `evidence.unlock` when allowed).

The manifest carries geometry and mask tokens only, never text. Coordinates are in PDF points, top-left origin, in unrotated page space. The client scales by `image_w / width_pt`.

### 3.4 Pages, regions and search
- **Page:** a masked PNG, 1,240 px wide, served `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`. No JSON body.
- **`RegionsOut`:** `items[]` holds `{match_id, page, rects: [[x0, top, x1, bottom]], citation_id, label?}`. Rects are in page points; a table cell is `{sheet, cell}`. All I, except `label` C.
- **`SearchOut`:** `items[]` holds `{page, rects}`, plus `total` and `truncated`, all I. There are at most 200 hits and no text. The query string is never logged.

### 3.5 Reveal and unlock
- **`RevealIn`:** `region_id` I, `context_ref?` I (a citation or anchor).
- **`RevealOut`:** `mask_id` I, `value` **R** (the only schema that carries an unmasked PII value), `kind` I, `expires_in` I (30 for the viewer surface), `revealed_by` I, `revealed_at` I. Served `Cache-Control: no-store`.
- **`UnlockIn`:** `password` **R**, a `SecretStr`. It is never logged, stored, put in a Temporal payload, sent to error tracking, or echoed back.
- **`UnlockOut`:** `status` I is `ready` or `wrong_password`. `attempts_left` I.

### 3.6 Reserved create (`POST /v1/citations`, 501)
**`CitationCreateIn`:** `cited_from_ref` I, `cited_from_locator` I, `kind` (`document_text` only), `locator: {evidence_version_id, page, bbox}` I. The server derives the quote from the layer and ignores any text the client sends. The frozen shape for P-04 is the `CitationDisplay` response.

## 4. Status words
The words live in `docs/product/status-vocabulary.yaml` (C2; DF-31). The C4 stub PR (P-03-T02) adds them, tied to its route models. This doc only references them. The codes are:

- `CitationV2Out.state`: `valid`, `moved`, `broken`, `relinked`.
- `ViewerManifestOut.status`: `processing`, `ready`, `password_protected`, `unreadable`, `not_previewable`.
- `EvidenceUnlockOut.status`: `ready`, `wrong_password`.

The display words the screens need (P-03 §4.10, DF-31) are:
- citation: Unverified (`verified=false`) · Source moved (`moved`) · Broken (`broken`);
- viewer: Processing… (`processing`) · Password-protected (`password_protected`) · Can't preview (`unreadable`, `not_previewable`);
- reveal: Revealed · logged.

The YAML is the authority for labels. Never invent a synonym.

## 5. Human-only actions
`citation.relink`, `citation.create`, `pii.reveal` and `evidence.unlock` are refused to agent principals, system principals, and any call outside a live API request (INV-1). Each is enforced in up to three layers:
- **matrix:** agent is denied;
- **`serving_request()`:** the service-level guard, the REVIEW-001 evidence-decision pattern;
- **database:**
  - `citation_events` has CHECK `kind <> 'relinked' OR actor_kind = 'human'`;
  - `pii_reveals.user_id` is NOT NULL, and there are no agent or system rows;
  - `evidence_derivations.created_by_user_id` is NOT NULL.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | flag off; a walled, invisible, other-firm or unknown citation or version (DEC-43). Stacks omit it with no count |
| 403 | `{"detail": "forbidden", "facts": {"reason": "role"}}` | the action is not held. A client principal gets this on every citation route |
| 403 | `{"detail": "forbidden", "facts": {"reason": "offshore"}}` | an offshore member on a reveal or an unscannable page |
| 403 | `{"detail": "forbidden", "facts": {"reason": "mfa_required"}}` | a TIN-kind reveal with MFA older than the window; the shell runs step-up and retries |
| 409 | `{"detail": "preview_outdated"}` | the page was rendered before masking existed, until the backfill re-renders it |
| 409 | `{"detail": "active_content"}` | the manifest, a page, regions or search of a PDF with active content (DEC-296): kept, never shown |
| 409 | `{"detail": "not_password_protected"}` | unlock on a version that is not locked |
| 409 | `{"detail": "not_moved"}` | relink on a citation whose state is not `moved` |
| 422 | `{"detail": "relink_unverified"}` | the old text is not on the successor; the UI offers "Open source" |
| 429 | `{"detail": "reveal_rate_limited"}` | the 21st reveal by one user in an hour |
| 429 | `{"detail": "unlock_rate_limited", "facts": {"retry_after": …}}` | 5 failed unlocks in 15 minutes |
| 501 | `{"detail": "not_implemented"}` | `POST /v1/citations` (reserved) |

The 403 reasons are `role`, `offshore` and `mfa_required` (P-03 §8.1). The exact facts key is per the stub PR. A wrong password is not an error: it returns 200 `{status: wrong_password, attempts_left}`.

## 7. Audit and outbox events
Every write goes through the unit of work (ADR-007). No event carries Restricted values (DEC-60).

| Event | Kind | Written when | Payload |
|---|---|---|---|
| `citation.created` | audit | a citation row is written (by an agent or a human) | ids, kind, verified, reason; no quote |
| `citation.relinked` | audit | a human relinks | old and new citation ids, the person |
| `citation.moved` | audit (system) and outbox | the moved detector writes a `moved` event | citation id, cause ref; identifiers only |
| `citation.broken` | audit (system) | a source is voided, withdrawn or erased | citation id, cause ref |
| `pii.revealed` | audit only, **never fanned out** | a reveal succeeds | viewer, version, region id, kind, last4, context ref; **never the value**. It also writes a Q-02 `access_events` row |
| `evidence_version.unlocked` | audit and outbox | an unlock succeeds | version id, derivation id, the person |
| `evidence_version.unlock_failed` | audit | an unlock attempt fails | version id, attempt count only; never the password |
| `evidence_version.read` | audit (exists) | a download from ⋯ | unchanged |

`evidence_version.created` already exists; the moved detector subscribes to it. Workflow writes of derived records follow the existing system-audited `upload_extractions` pattern.

## 8. Example payloads
Brightwater Hale, synthetic. Ids are placeholders. The seed holds no real TIN (blueprint §9).

`GET /v1/citations/{id}` (SHL-07a; the AUD-05 guidance citation is SHL-07c):
```json
{"id": "…", "n": 1, "kind": "methodology_step", "title": "BH-EBP-110: General Planning Procedures",
 "loc": "…", "quote": null, "quote_state": "shown", "value_text": null, "match_id": "ms:…@…",
 "state": "valid", "verified": true, "verification_reason": null,
 "created_by": {"kind": "agent", "label": "Hannah Leclerc via Agent"}, "retrieved_at": "…",
 "source": {"type": "methodology_template_version", "id": "…", "version": "2"},
 "used_in": 1, "moved": null, "allowed_actions": []}
```

The moved case (SHL-07e): `"state": "moved"`, `"moved": {…}`, rendering "Source moved — BH-EBP-110 v2 was superseded by EBP v3 on Jan 1, 2026", and `"allowed_actions": ["citation.relink"]` for Hannah.

`GET /v1/evidence-versions/{v}/regions?match_ids=…` (SHL-08b): one item lit for TOTAL INVESTMENTS 16,500,000.00 on the Harborline statement. Its linked figures foot: 14,895,000.00 + 1,605,000.00 = 16,500,000.00.

`GET /v1/evidence-versions/{v}/viewer` for Claire's W-2 (SHL-08c): `"status": "ready"`, `"pii_masks": [{"id": "…", "page": 1, "rect": [...], "kind": "ssn", "display": "•••-••-6081"}]`, `"allowed_actions": ["pii.reveal"]` for Samuel Ito. For an offshore member, `allowed_actions` omits `pii.reveal`.

`POST …/pii-reveals` `{"region_id": "…"}` returns `{"mask_id": "…", "value": "000-00-6081", "kind": "ssn", "expires_in": 30, "revealed_by": "…", "revealed_at": "…"}`. The UI reads "Revealed by Samuel Ito · 9:31 AM · logged to the audit trail".

The Halvard consolidated 1099 (SHL-08d) has manifest `"status": "password_protected"`. `POST …/unlock` with a wrong password returns `{"status": "wrong_password", "attempts_left": 4}`.

A version still processing (SHL-08e) has manifest `"status": "processing"`; the client polls every 3 s.

## 9. Consumer contract tests
- **pytest, P-03-T03:** `backend/tests/contracts/c04_citations_viewer/`. It covers the shapes, the refusal codes in §6, the human-only actions in §5, the audit event names in §7, and the footing figures 14,895,000.00 + 1,605,000.00 = 16,500,000.00 and 6,200 × 25% = 1,550.
- **TypeScript fixture assertions:** F-05-T44.

Both run in the provider's CI and stay green through every later P-03 PR (SPEC-322 AC-41, AC-42).

## 10. Versioning
Additive changes go in place. Breaking changes ship as C4 v2 with one sprint of overlap (see `docs/contracts/README.md`).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | contract doc 2026-10-23 (P-03-T01); stub P-03-T02; freeze S5 |

## 11. Open points
- **DEC-147** (ADR-166): the ten kinds, no stored quote, computed state, relink human-only, and the reserved `annotation_id` and create.
- **DEC-148:**
  - the file name `c04-citations-viewer.md`, which replaces the register's planned `citation-v2.md`;
  - one flag per route family (§2);
  - `unreadable` shares "Can't preview" (the words themselves land with the C4 stub);
  - P-03 §11.2 OQ-1 to OQ-8 decided with the plan's recommendations: a reveal lasts 30 s on the viewer, with `reason_code=source_review` and no free text; v1 relinks only to the successor; `eqr_reviewer` and `reviewer` read citations, and `client_service` does not; firm-level citations take visibility from their anchor provider; auto-highlight is per browser; the reveal limit is 20 per hour; unlock adds no re-screening trigger.
- The `register_citing_anchor(anchor_type, provider)` slot is inferred and lands with P-04.
