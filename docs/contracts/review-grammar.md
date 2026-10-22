# C3 · Review grammar (v1)

| Field | Value |
|---|---|
| Register row | C3 in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub. Part 1 (sign-offs, review notes, human gates) is P-04-T07. Part 2 (decision cards, proposals, suggestions) is P-04-T08. Part 3 (issues, checkpoints, field provenance) is P-04-T11 |
| Provider epic | P-04 (`review` module; `agents` for suggestions and proposals, ADR-161) |
| Consumers | SHL-09, SHL-10, SHL-11, SHL-12, SHL-15, SHL-16 (P-04 UI); AUD-17 (A-06); HOME-01/02 (I-01); A-04, A-05, A-07, T-01, T-02, T-04, C-01, C-02, K-03, K-04 |
| Freeze sprint | Schema S3: recorded frozen by Fri Dec 11, 2026 (P-04-T09). Services S12: Fri Apr 16, 2027 (P-04-T27) |
| Flag | `review.grammar_api` (default off, expires 2027-01-20) |
| Spec | `docs/plan/epics/P-04.md` §3 (F1 to F5, F9), §4.3, §4.5 |
| ADRs | ADR-160 (review grammar, P-07), ADR-161 (suggestions, proposals, approval grants, Undo, P-35), P-36 (API conventions), ADR-031 (classification), ADR-089 (flags), ADR-005 (agents propose) |

## 1. Purpose
Every service line records a human judgement on prepared work the same way. A sign-off is a level on a ladder, bound to the content hash the signer saw. A review note blocks sign-off until a person clears it. The Home counts come from one projection. Consumers build SHL-12, AUD-17 and HOME-02 against these shapes in fixture mode while the services land. No route here lets an agent, system or support principal sign, clear or decide (INV-1).

## 2. Who may call it
Part 1 (P-04-T07). Every route is behind `review.grammar_api`. Off, it answers 404. On, it answers 501 `not_implemented` until its service lands: sign-offs in P-04-T18, notes in P-04-T21, the projection in P-04-T16.

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Sign-off ladder | `GET /v1/sign-offs?target_type=&target_id=` | `sign_off.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer (independence required) | denied |
| Eligibility for one level | `GET /v1/sign-offs/eligibility?target_type=&target_id=&level=` | `sign_off.read` | as above | denied |
| Record a sign-off | `POST /v1/sign-offs` | `sign_off.create`, then the level row in the service: L1 `sign_off.prepare`, L2 `sign_off.review`, L3 `sign_off.manager`, L4 `sign_off.partner`, L5 `sign_off.eqr` | the level row's roles | denied at every layer |
| Bulk sign-off | `POST /v1/sign-offs:bulk` with `Idempotency-Key` | `sign_off.bulk` | senior, manager, engagement partner | denied |
| Review notes, list | `GET /v1/review-notes?target_type=&target_id=&engagement_id=&status=&cursor=&limit=` | `review_note.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |
| Review note, detail | `GET /v1/review-notes/{note_id}` | `review_note.read` | as above; reading the sealed body is an access event (Q-02) | denied |
| Raise | `POST /v1/review-notes` | `review_note.raise` | engagement partner, manager, senior, reviewer | denied |
| Respond | `POST /v1/review-notes/{note_id}/respond` | `review_note.respond` | engagement partner, manager, senior, staff, reviewer | denied |
| Clear | `POST /v1/review-notes/{note_id}/clear` | `review_note.clear` | engagement partner, manager, senior, reviewer; only the raiser (service) | denied (and the event's CHECK) |
| Withdraw | `POST /v1/review-notes/{note_id}/withdraw` | `review_note.withdraw` | engagement partner, manager, senior, reviewer; only the raiser (service) | denied |
| What waits on me | `GET /v1/human-gates?assignee=me&kind=&engagement_id=&cursor=&limit=` | `human_gate.read` | firm admin, practice leader (in scope), quality partner, engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |

**Level actions (DEC-135).** The plan names the level actions `sign_off.l1` to `sign_off.l5`. The matrix already holds them as `sign_off.prepare`, `sign_off.review`, `sign_off.manager`, `sign_off.partner` and `sign_off.eqr` (SPEC-308), and live workpaper, trial-balance and mapping routes declare them. C3 keeps those names, so each level has one row and there are no aliases. Wherever the plan writes `sign_off.l<n>`, read the matching row above.

**Conditions arriving later.** P-04-T15 adds the matrix conditions `not_preparer_of_target` (L2, L3) and `reserved_role`, plus the generated I-AGENT-NEVER tests for every resolution action. Until then the service enforces segregation (R-SO-3).

The SPEC-313 routes under `/v1/engagements/{engagement_id}/review-notes` stay live. They are retired when the notes UI (A-06) reads `/v1/review-notes`.

## 3. Models
Code: `backend/src/abacus/modules/review/contract.py`.

**Sign-offs**

- **`SignOffTargetOut`**. Confidential: `label` ("Trial Balance") and `context_label` ("Northwind Robotics 401(k) Plan · PY2025"). Internal: `target_type`, `target_id`, `version_no`, `content_hash`, `cell_count`, `citation_count`.
- **`SignOffOut`**, one insert-only row. All fields are internal:
  - `id`, `target_type`, `target_id`, `kind` (`ladder`, `field_tick` or `final_approval`);
  - `level` (`L1_preparer`, `L2_reviewer`, `L3_manager`, `L4_partner` or `L5_eqr`);
  - `signer_user_id`, `signer_name`, `initials`, `signed_at`;
  - `content_hash`, `version_no`, `statement_version`;
  - `adopted_run_id` and `adopted_run_number`, set on an L1 that adopts agent work (R-SO-8);
  - `stale`, which is computed: the row's hash differs from the target's current hash. No sign-off row is ever updated.
- **`LadderLevelOut`** (internal): `level`, `required`, `expected_signer_user_id`, `expected_signer_name`, and `latest`, which is a `SignOffOut` or null.
- **`SignOffLadderOut`**: `target`, `levels[]` and `allowed_actions[]`.
- **`SignOffEligibilityOut`**: `target`, `level`, `levels_allowed[]`, `ladder[]`, `checks[]`, `eligible` and `statement {version, text}`.
  - **`EligibilityCheckOut`**: `code`, `result` (`pass`, `fail` or `warn`), `facts` and `refs[]`.
  - The check codes are `open_review_notes`, `independence`, `segregation`, `all_cited`, `gate_g4`, `open_issues` and `eqr_limits`.
  - `facts` is Confidential. It holds the counts, names and dates the row's sentence needs. `refs` holds identifiers only: the open notes, the issues.
- **`SignOffIn`** (internal): `target_type`, `target_id`, `level`, `kind` (default `ladder`), `seen_hash` and `statement_version`. `seen_hash` is `sha256:` followed by the 64-hex digest (ADR-160 clause 3).
- **`BulkSignOffIn`**: `targets[] {target_type, target_id, seen_hash}` (1 to 50 targets), `level` and `statement_version`.
- **`BulkSignOffOut`**: `results[] {target_type, target_id, ok, sign_off_id, detail}`, `signed` and `excluded`. `detail` is one of the exclusion codes in §6.

**Review notes**

- **`ReviewNoteItemOut`**, a list row. Internal: `id`, `engagement_id`, `target_type`, `target_id`, `status`, `raised_by_user_id`, `raised_by_initials`, `raised_at`, `assignee_user_id`, `allowed_actions`. Confidential: `anchor {kind, ref}`, where `kind` is `cell`, `field`, `section` or `region` and `ref` is, for example, `RA!C14`.
- Bodies are sealed and Restricted. **List rows never carry a body.** `ReviewNoteOut` (the detail, and the response of every write) carries `note`, `body` (Restricted) and `events[] {event, body (Restricted), actor_user_id, actor_name, at}`. `event` is one of `raised`, `responded`, `cleared`, `closed`, `withdrawn` or `reopened`.
- **`RaiseReviewNoteIn`**: `target_type`, `target_id`, `anchor?` (Confidential), `body` (Restricted, 1 to 2,000 characters, no control characters) and `assignee_user_id?`.
- **`ReviewNoteEventIn`**: `body?` (Restricted).
- The list is the P-36 envelope. `counts` are per status.

**Human gates (C13 read)**

- **`HumanGateOut`** (internal): `id`, `kind`, `subject {type, id}`, `engagement_id`, `work_item_id`, `client_id`, `assignee_user_id`, `role`, `due_on`, `state` (`open`, `done` or `voided`) and `created_at`.
- `kind` is one of `decision`, `sign_off_request`, `proposal`, `send`, `final_approval`, `export` or `release` (DF-25).
- Labels come from the subject's owner at read time; the projection stores none.
- The list is the P-36 envelope. `counts` are per kind, so Home's "Waiting on you: 3 decisions, 6 sign-offs, 2 exports" is the same 11 on every surface.

## 4. Status words
From `docs/product/status-vocabulary.yaml` (P-04-T02):

- `sign_off_slot`: `signed` ("✓ {initials}") and `stale` ("Changed after sign-off"). Both are derived and never stored.
- `review_note`: `open`, `responded`, `cleared`, `closed`, `withdrawn` (the generated `ReviewNoteStatus`).

## 5. Human-only actions
`sign_off.create`, `sign_off.bulk`, the five level rows, and `review_note.raise`, `.respond`, `.clear` and `.withdraw` all deny the agent. The sign-off rows and `review_note.withdraw` also deny `system` explicitly. Every other principal, support included, holds no cell, so it is denied.

The services add the other layers of ADR-160 clause 12:
- `require_live_human` comes first;
- `sign_offs.actor_kind = 'human'` is a CHECK bound to `app.actor_kind` (migration 0093);
- a `cleared` note event requires a human;
- the `SIGNOFF-001` static rule (P-04-T18).

Agent work is never shown as a sign-off. It is "Performed by Agent run #n under the direction of ‹person› · adopted by ‹initials›" on the L1 that adopted it.

## 6. Errors
Every route on this page also answers:
- 404 `{"detail": "not found"}` when the flag is off, and for a walled or foreign target;
- 501 `{"detail": "not_implemented"}` when the flag is on and the service has not landed.

Fixed codes the services will answer:

| Status | Body | When |
|---|---|---|
| 409 | `{"detail": "content_changed"}` | the target's current hash differs from `seen_hash`; nothing is written |
| 409 | `{"detail": "open_review_notes", "facts": {"count": 2}}` | L2 and above while notes are open (R-SO-4) |
| 409 | `{"detail": "segregation"}` | the preparer at L2 or L3; the EQR at L1 to L4; the engagement partner as EQR (R-SO-3) |
| 409 | `{"detail": "independence_pending"}` | no current independence confirmation (R-SO-5, G2) |
| 409 | `{"detail": "incomplete"}` | an empty required field (R-SO-6) |
| 422 | `{"detail": "uncited_change", "facts": {"rows": [...]}}` | an uncited value (R-SO-6) |
| 403 | `{"detail": "level_not_permitted"}` | the level's row denies the caller (R-SO-2) |

Bulk items carry the same codes in `results[].detail`.

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `sign_off.recorded` (audit and outbox) | each sign-off, once per item in bulk | sign-off id, target type and id, level, content hash |
| `sign_off.resigned` (audit) | a new row at a level whose last row was stale | sign-off id, the stale row's id |
| `sign_off.went_stale` (outbox) | the target's hash moves past a signer's (P-04-T19) | sign-off id, target |
| `review_note.raised`, `.responded`, `.cleared`, `.withdrawn` (audit and outbox) | each note event | note id, target, event |

Reads of sealed note bodies are access events (Q-02 `access_events`). Notification kinds `sign_off_requested`, `sign_off_stale` and `review_note_raised` come from P-04-T26 (C16).

## 8. Example payloads
Brightwater Hale E0: Northwind Robotics 401(k) Plan, PY2025, Mon Sep 14, 2026, 9:41 AM CT. Viewer Hannah Leclerc. Ids are placeholders, and the seed fixes them when P-04-T36 loads the scenario.

The content hash is written as SHL-12 shows it, `sha256:9f4c…e21a`. On the wire it is the full 64-hex digest, which the seed computes from Trial Balance v1's content (ADR-160 clause 3).

**SHL-12 a. Eligibility, Trial Balance v1 at L2.**
`GET /v1/sign-offs/eligibility?target_type=workpaper&target_id=<tb>&level=L2_reviewer`
```json
{"target": {"target_type": "workpaper", "target_id": "<tb>", "label": "Trial Balance",
            "context_label": "Northwind Robotics 401(k) Plan · PY2025", "version_no": 1,
            "content_hash": "sha256:9f4c…e21a", "cell_count": 14, "citation_count": 3},
 "level": "L2_reviewer",
 "levels_allowed": ["L1_preparer", "L2_reviewer", "L3_manager", "L4_partner"],
 "ladder": [
   {"level": "L1_preparer", "required": true, "expected_signer_user_id": null, "expected_signer_name": null,
    "latest": {"id": "<so-1>", "target_type": "workpaper", "target_id": "<tb>", "kind": "ladder",
               "level": "L1_preparer", "signer_user_id": "<marcus>", "signer_name": "Marcus Delaney",
               "initials": "MD", "signed_at": "2026-09-14T14:33:00Z", "content_hash": "sha256:9f4c…e21a",
               "version_no": 1, "statement_version": "<statement>", "adopted_run_id": "<run>",
               "adopted_run_number": 4127, "stale": false}},
   {"level": "L2_reviewer", "required": true, "expected_signer_user_id": null, "expected_signer_name": null, "latest": null},
   {"level": "L3_manager", "required": false, "expected_signer_user_id": null, "expected_signer_name": null, "latest": null},
   {"level": "L4_partner", "required": true, "expected_signer_user_id": "<margaret>", "expected_signer_name": "Margaret Okonkwo", "latest": null},
   {"level": "L5_eqr", "required": true, "expected_signer_user_id": "<thomas>", "expected_signer_name": "Thomas Whitcombe", "latest": null}],
 "checks": [
   {"code": "open_review_notes", "result": "pass", "facts": {"count": 0}, "refs": []},
   {"code": "independence", "result": "pass", "facts": {"person": "Hannah Leclerc", "confirmed_on": "2026-08-03"}, "refs": []},
   {"code": "segregation", "result": "pass", "facts": {"preparer": "Marcus Delaney"}, "refs": []},
   {"code": "all_cited", "result": "pass", "facts": {"cited": 14, "cells": 14}, "refs": []},
   {"code": "gate_g4", "result": "warn", "facts": {"awaiting": "Margaret Okonkwo"}, "refs": [{"type": "decision_card", "id": "<materiality-card>"}]}],
 "eligible": true,
 "statement": {"version": "<statement>", "text": "I reviewed this work. It is sufficient and appropriate, and its conclusions are supported."}}
```
SHL-12 renders the L1 detail as "Performed by Agent run #4127 under the direction of Marcus Delaney · adopted by MD".

**SHL-12 a′. Sign.**
`POST /v1/sign-offs`
```json
{"target_type": "workpaper", "target_id": "<tb>", "level": "L2_reviewer", "kind": "ladder",
 "seen_hash": "sha256:9f4c…e21a", "statement_version": "<statement>"}
```
The 201 response:
```json
{"id": "<so-2>", "target_type": "workpaper", "target_id": "<tb>", "kind": "ladder", "level": "L2_reviewer",
 "signer_user_id": "<hannah>", "signer_name": "Hannah Leclerc", "initials": "HL",
 "signed_at": "2026-09-14T14:41:00Z", "content_hash": "sha256:9f4c…e21a", "version_no": 1,
 "statement_version": "<statement>", "adopted_run_id": null, "adopted_run_number": null, "stale": false}
```
The screen then shows the toast "Signed off Trial Balance (L2) · 9:41 AM" and the header "✓ MD ✓ HL".

**SHL-12 b. Blocked by open notes (Risk Assessment v1).**
- The check row: `{"code": "open_review_notes", "result": "fail", "facts": {"count": 2}, "refs": [{"type": "review_note", "id": "<ra-c14>"}, {"type": "review_note", "id": "<ra-c22>"}]}`.
- A sign-off answers `409 {"detail": "open_review_notes", "facts": {"count": 2}}`.
- The two notes, from `GET /v1/review-notes?target_type=workpaper&target_id=<ra>&status=open`:
```json
{"items": [
  {"id": "<ra-c14>", "engagement_id": "<northwind>", "target_type": "workpaper", "target_id": "<ra>",
   "anchor": {"kind": "cell", "ref": "RA!C14"}, "status": "open", "raised_by_user_id": "<hannah>",
   "raised_by_initials": "HL", "raised_at": "<time>", "assignee_user_id": "<marcus>", "allowed_actions": ["review_note.clear"]},
  {"id": "<ra-c22>", "engagement_id": "<northwind>", "target_type": "workpaper", "target_id": "<ra>",
   "anchor": {"kind": "cell", "ref": "RA!C22"}, "status": "open", "raised_by_user_id": "<margaret>",
   "raised_by_initials": "MO", "raised_at": "<time>", "assignee_user_id": "<marcus>", "allowed_actions": []}],
 "next_cursor": null, "total": 2, "total_capped": false, "counts": {"open": 2}, "facets": {}}
```
- The detail of the first note (`GET /v1/review-notes/<ra-c14>`) has `"body": "Explain why participant loans are not a significant risk"`.

**SHL-12 c. Same preparer.** Marcus Delaney asks for L2 on Trial Balance. The check row is `{"code": "segregation", "result": "fail", ...}`, and a sign-off answers `409 {"detail": "segregation"}`. The dialog reads "You prepared this workpaper. A different reviewer must sign L2."

**SHL-12 e. Stale after change** (Thu Sep 24, 2:15 PM). Contributions receivable of $48,600 were added, so net assets are now $16,861,000 and Trial Balance's hash moved. Hannah's L2 row reads `"stale": true`, and SHL-12 offers only "Re-sign as Reviewer (L2)", which writes a new row.

**SHL-12 f. Bulk** (Thu Sep 24). The six rows are Trial Balance v1, Service Organizations & SOC 1 v1, Materiality v2, General Audit Planning v1, Internal Control v1, and Investments & Certification v1. Three are excluded with reasons, so the response has `"signed": 3, "excluded": 3`:
- Service Organizations & SOC 1 is `incomplete` ("Waiting on inputs");
- one is `open_review_notes` ("1 open note");
- one is `segregation` ("You prepared this").

**SHL-12 g. EQR viewer.** For Thomas Whitcombe, `levels_allowed` is `["L5_eqr"]`, and L1 to L4 answer `403 {"detail": "level_not_permitted"}`.

**Home.** `GET /v1/human-gates?assignee=me` returns `"counts": {"decision": 3, "sign_off_request": 6, "export": 2}`, which reads "Waiting on you: 3 decisions, 6 sign-offs, 2 exports".

## 9. Consumer contract tests
`backend/tests/contracts/review_grammar/` (P-04-T09) covers the SHL-10 a–g, SHL-11 a–h and SHL-12 a–h shapes against the stubs. The TypeScript fixture assertions run in the provider's stage 2. They fail if a field the artboards need is removed.

## 10. Versioning
Additive changes go in place. Breaking changes ship as v2 with one sprint of overlap.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S3, Fri Dec 11, 2026) | | 2026-10-22: part 1 stub (P-04-T07): sign-offs, review notes and human gates |

## 11. Open points
- **Level actions.** The level actions keep their SPEC-308 names rather than `sign_off.l1` to `l5` (DEC-135).
- **Note bodies.** Note bodies are Restricted, so the list carries none. A detail route, `GET /v1/review-notes/{note_id}`, is added beyond the plan's table. Each body read is then one access event.
- **`sign_off.eqr` cell.** The row allows `reviewer` (SPEC-308). The F-03-T23 role `eqr_reviewer` is added to the reads and to `sign_off.create`. Moving `sign_off.eqr` to `eqr_reviewer` is P-04-T15's, with the generated deny tests.
- **Flag expiry.** `review.grammar_api` expires 2027-01-20, within the plan's Jan 1 to Apr 20 window, which it avoids for flags that live firms use. Live firms do not use this flag before the C3 services land. Its renewal moves the expiry past Apr 20.
