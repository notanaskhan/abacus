# Workpaper core API (internal; v1)

| Field | Value |
|---|---|
| Register row | internal workpaper core API (A-04 §8.2; consumed by A-05 and A-08 as their cell store) in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub (A-04-T01, 2026-10-31); live per route with A-04-T04 (record, versions, cells, export), T07 (procedures and tailoring), T11 (drafts) and T19 (attention flags) |
| Provider epic | A-04 |
| Consumers | AUD-04, AUD-05, AUD-09 (the cell store), AUD-02 rail (section states), KNW-03 d (tailoring), SHL-07 and SHL-08 (citations), SHL-09 (field history), SHL-12 (sign-off ladder); A-05 EBP workpapers, A-08 fieldwork |
| Flags | `workpapers.core` (every route); `workpapers.drafting` too for `POST …/drafts` (default off; DEC-137 override, expires 2027-04-29) |
| Spec | A-04 §3.1, §4.3 (SPEC to land with A-04-T02) |
| ADRs | ADR-005, ADR-031, ADR-042, ADR-050, ADR-052, ADR-160, ADR-161 |

## 1. Purpose
One workpaper cell store with stable addresses (`sheet_key` + `cell_key`, "Exceptions!D2"),
insert-only versions with a producer and a cause, and sign-off staleness from the owner's content
hash, so A-05 and A-08 reuse it. Cells are written only through `review.api.record_value` (field
history on SHL-09). An agent value is a pending **suggestion** until a person adopts it (ADR-005);
the L1 sign-off that adopts it is a person's act (R-SO-8).

## 2. Who may call it
All under `/v1/engagements/{eid}`. Every client and third-party principal and `client_service`
answer 404 (INV-4, DEC-20); a walled member 404 and an independence failure 403 (INV-3).

| Operation | Method and path | Matrix action | Roles allowed | Agent or system |
|---|---|---|---|---|
| Section states | `GET /workpaper-states?kind=` | `workpaper.read` | EP, manager, senior, staff, reviewer | firm roles only today; agent through its own task reads later |
| Record projection | `GET /workpapers/{id}/record?tab=&version=` | `workpaper.read` | as above | as above |
| Versions | `GET /workpapers/{id}/versions` | `workpaper.read` | as above | as above |
| Edit cells | `PATCH /workpapers/{id}/cells` (`Idempotency-Key`, `expected_version`) | `workpaper.edit` | EP, manager, senior, staff | denied |
| Start a draft | `POST /workpapers/{id}/drafts` (202 + run id) | `workpaper.draft` | EP, manager, senior | denied |
| Export | `GET /workpapers/{id}/export.xlsx?version=` | `workpaper.export` | EP, manager, senior, staff, reviewer, EQR | denied |
| Convert a flag | `POST /workpapers/{id}/flags/{flag}/convert` `{to}` | `attention_flag.convert` | EP, manager, senior, staff | denied |
| Remind | `POST /workpapers/{id}/flags/{flag}/remind` | `follow_up.draft` (existing) | as that action | as that action |
| Procedures and tailoring | `GET /program-tailoring?program=` | `procedure.read` (fieldwork's) | team, reviewer | agent `task_scope` |
| Tailor a step | `PATCH /procedures/{id}` `{expected_version, tailored, rationale}` | `procedure.tailor` | EP, manager | denied |

**Live routes kept (DEC-1757).** The SPEC-308 operations in `workpapers/routes.py` (`GET` and
`POST /workpapers`, `GET /workpapers/{id}`, `PUT /workpapers/{id}/cells`, citations, the five
sign-off routes) and fieldwork's SPEC-300 `GET /procedures` and `GET /procedures/{id}` stay on
their paths, unflagged. A-04's reads that the plan wrote on those same paths take paths no live
route holds: the list with section states is `GET /workpaper-states`, the projection
`GET /workpapers/{id}/record`, and one procedures read, `GET /program-tailoring`, serves both
AUD-04 and KNW-03 d. A-04-T04 moves AUD-04 onto them; the SPEC-308 routes retire with their last
consumer, never renamed in place. The workpaper is addressed by its id, as the live routes do;
`code` ("GAP", "RA", "IC", "SO") is unique per work item and shown.

## 3. Models
`backend/src/abacus/modules/workpapers/contract.py`; every field classified (ADR-031). Cell values,
flag text and rationales are `confidential`; ids, keys, hashes and states `internal`. No
Restricted value is stored in a cell.

- `WorkpaperStateOut` (id, code, kind, title, `current_version_no`, `SectionStateOut[]` with the
  `audit_section` word and `waiting_on_request_ids`, AC1.8).
- `WorkpaperRecordOut` (code, kind, title, audit area, `program_step_keys`, version and current
  version, `content_hash`, tab, sections, `WorkpaperCellOut[]`, `AttentionFlagOut[]`,
  `SignOffRungOut[]` with `stale`, `allowed_actions`).
- `WorkpaperCellOut` (`sheet_key`, `cell_key`, section, row and column keys, `TypedValue {t, v}`
  where `v` is a string and amounts are decimal strings from code, `value_source`, `value_state`,
  `suggestion_id`, `tickmarks`, `citation_ids`, `updated_version_no`).
- `WorkpaperVersionOut` (`version_no`, `content_hash`, `produced_by_kind`, `agent_run_id`,
  `created_by_name`, `on_behalf_of_name`: "Marcus Delaney via Agent", `cause`).
- `CellsEditIn {expected_version, cells: [{sheet_key, cell_key, value, reason}]}`: `reason` is
  required to override an agent value.
- `WorkpaperDraftIn {mode ∈ gap · risk_narrative · risk · ic · soc1, section_key}`,
  `WorkpaperDraftStartedOut {run_id, status: queued}`.
- `FlagConvertIn {to ∈ request_draft · review_note}`, `FlagConvertedOut {flag, draft_id}`.
- `ProgramProcedureOut` (program code, step key and number, pinned version, level — the program
  step's foundation · planning · testing · completion, DEC-1761 — mandatory, tailored, rationale,
  status, `linked_work`), `TailorIn`. The table is `audit_procedures` (0581).

## 4. Status words
`workpaper_value_state` (empty, suggested, adopted, edited, human), `attention_flag` (open
"PBC GAP", converted, resolved) and `audit_procedure` (not_started, in_progress, in_review,
complete), generated from `docs/product/status-vocabulary.yaml`; sections use the existing
`audit_section` words.

## 5. Errors
`version_conflict`, `drafting_not_enabled`, `pack_configuration_error` (with the exact AUD-09 d
text), `mandatory_step`, `flag_already_converted` (409); `reason_required`, `rationale_required`
(422). Each lands with the task that raises it; the stub raises only 404 and 501
`not_implemented`.

## 6. Human-only actions and audit events
Human only: every write in §2 (the agent writes suggestions through its own channel, ADR-005).
Audit: `workpaper.created`, `workpaper_version.created`, `workpaper.exported`,
`attention_flag.raised/converted/reminded/resolved`, `procedure.tailored`,
`section_draft.started/failed`. Outbox: `workpaper.version_created` (staleness and the re-draft
consumer).

## 7. Stub behaviour (A-04-T01)
Client principal 404 → the route's action on the engagement → 404 with `workpapers.core` off (and
`workpapers.drafting` off for drafts) → 501 `not_implemented`.

## 8. Example (Brightwater Hale, Northwind Robotics 401(k) Plan, PY2025)
The Keystone Retirement Services cell on General Audit Planning (AUD-04 a) after a `gap` draft:
`{sheet_key: "gap", cell_key: "S4.R2.value", value: {t: "text", v: "Keystone Retirement Services"},
value_source: "agent", value_state: "suggested", tickmarks: ["◌"], citation_ids: [<BH-EBP-110
step 4 at v3>, <SOC 1 p.14 section III>]}`; after Marcus's L1 adoption it reads `value_state:
"adopted"` with an ink-3 ✓.
