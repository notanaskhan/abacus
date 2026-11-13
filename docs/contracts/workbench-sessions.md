# Workbench sessions family (additive to C6 v2)

- **Status:** stub (W-02-T02, TASK-7604, 2026-11-12; DEC-4604). Marked final at W-02-T29.
- **Provider:** `workbench` (list, create, rename, delete, context; amber) and `agents` (drill,
  run-artifact preview and download; red). **Spec:** SPEC-653. **Epic:** W-02 §4.3, §8.2.
- **Callers:** WB-01, WB-02, WB-03 (`apps/web/src/domain/workbench/`, W-02-T08); SHL-02 "New
  session…" (P-02); HOME-01's "3 running" pill (`/workbench?filter=running`, I-01); SHL-04
  notifications (`run_needs_input`, `run_finished` deep links). Not the portal: every route
  answers 403 to a portal principal and the portal bundle imports no workbench code (AC-V4).
- **Flags:** `workbench.enabled` gates every W-02 path (off: 404, and the screens render the
  designed flag-off state); `workbench.plans` gates plans and writes in the session workflow. The
  TAX-08 subject paths of the same routes (T-04, DEC-4316) are not gated by either.

## Routes

Every route goes through `AbacusRouter` with one action. Each answers, in order: the matrix
(403), `workbench.enabled` (404), then 501 until the row that serves it. Writes take
`Idempotency-Key`; rename takes `If-Match`.

| Method · path | Action | Body / query → response | Served by |
|---|---|---|---|
| `GET /v1/workbench/sessions` | `session.read` | `filter` (`all`, `mine`, `via_agent`, `running`, `needs_answer`), `q` (title only), `cursor` → `SessionListOut {items[SessionSummaryOut], next_cursor, total, counts {running, needs_answer}}`. With `subject_ref` instead: the TAX-08 list (unchanged) | W-02-T09 |
| `POST /v1/workbench/sessions` | `session.create` | `{}` (no `subject_ref`) → `SessionSummaryOut` (blank, `firm_wide`, title "New session"); with `subject_ref`: TAX-08 (unchanged) | W-02-T09 |
| `PATCH /v1/workbench/sessions/{id}` | `session.manage` | `{title}`, `If-Match` → `SessionSummaryOut` (`title_source: manual`); 409 `stale_version` | W-02-T09 |
| `DELETE /v1/workbench/sessions/{id}` | `session.manage` | → `SessionDeletedOut {id, deleted_at}` (soft) | W-02-T09 |
| `GET /v1/workbench/context-options` | `session.create` | `tab` (`client_record`, `documents`, `workpapers`), `q`, `session_id` → `ContextOptionsOut {tab, items[ContextOptionOut]}` | W-02-T10 |
| `POST /v1/workbench/sessions/{id}/context` | `session.manage` | `{items[{kind, ref_id}]}` (1–12) → `ContextItemsOut {session_id, firm_wide, items[ContextItemOut]}` | W-02-T10 |
| `DELETE /v1/workbench/sessions/{id}/context/{item_id}` | `session.manage` | → `ContextItemsOut` | W-02-T10 |
| `POST /v1/workbench/sessions/{id}/drill` | `session.manage` | `{artifact_id, group_key}` → `DrillOut {item_id, group_key, title, total, rows[DrillRowOut]}` | W-02-T20 |
| `GET /v1/run-artifacts/{id}/preview` | `run_content.read` | `sheet` → `ArtifactPreviewOut {artifact_id, file_name, sheets, sheet, columns, rows, footnote, sha256}` | W-02-T20 |
| `GET /v1/run-artifacts/{id}/download` | `run_artifact.download` | → the stored bytes; audited | W-02-T20 |

**Consumed from C6 v2, additive changes noted** (`agent-runs.md` §9): the snapshot
`GET /v1/workbench/sessions/{id}` (`locked`, `allowed_actions`), `POST …/messages` (W-02-T15 adds
`edit_of_item` and the context echo), the session and badge streams, the run commands, and
`POST /v1/agent-runs/{id}/steps/{sid}/retry` (W-02-T19 adds `scope: failed_items`).

## Models (every field classified)

- `SessionSummaryOut` (one list row): `id`, `title` (Confidential), `state` (registry
  `workbench_session`), `last_item_at`, `owner {user_id, name, via_agent}`, `origin`, `agent_label`
  (the definition's name on a via-Agent row), `needs_answer`, `running`, `ready_for_review`,
  `locked`, `title_source` (`auto`, `manual`), `version`, `context_count` (the Paperclip chip's
  attached items; null on a locked row; W-02-T14 rest, TASK-7927). The W-02 fields are optional
  so the TAX-08 list keeps its shape.
- `SessionListCountsOut {running, needs_answer}`: over the viewer's rows only.
- `ContextOptionOut {kind, ref_id, title, detail, attached}`; `ContextItemOut {id, kind, ref_id,
  card_title (Client record · Documents · Workpapers), chip_label, summary_lines[]}`. Kinds:
  `client`, `client_entity`, `engagement`, `request_set`, `document`, `workpaper_set`,
  `workpaper`.
- `DrillRowOut {ref_type: tax_return, ref_id, label, detail, href}`; `ArtifactPreviewOut` cells
  `{value, kind, bold}` as stored.

## Rules the provider keeps

1. **Membership (DEC-87, DEC-4601).** "All" = sessions I own or initiated + sessions whose owner
   shares a team or an office with me + sessions on work items whose team I am on. "Mine" = owned
   or initiated. "Via Agent" = origin not `manual`. Running and Needs your answer filter on the
   row flags.
2. **Walls (DEC-43, INV-3).** A row whose `client_scope` holds a client walled from the viewer is
   omitted from rows, counts, `total` and search; no "n hidden" figure exists in any response.
3. **Locked rows.** A non-walled client the viewer can't open: the row is listed with metadata
   only (`locked: true`; no figure, flag or count), and the snapshot answers `locked: true` with
   no item (AC-V1).
4. **Owner only.** Rename, delete, context and drill are the owner's; the snapshot's
   `allowed_actions` omits `manage` for anyone else, and the API answers 403 (AC-L5).
5. **Search** matches titles only, never thread content (AC-L3). Session titles also reach C15
   (`workbench_session`, cut item 1).
6. **Context options** list only records the viewer can open; summary lines are computed by code
   from the owning modules' APIs, never by a model (AC-C3, AC-C4).
7. **Delete is soft.** Items, runs and trace stay (AC-L4).
8. **No model call** in the list, context, drill or preview routes. The preview and the download
   read the stored artifact, never a re-render.

## Status words (C2)

`workbench_session` (Live, Running, Needs your answer, Ready for review, Complete, Failed);
`workbench_session_filter` (All sessions · Mine · Via Agent · Running {n} · Needs your answer {n});
`proposal.pending` `approval_card_owner` "Waiting on you", `approval_card_other` "Waiting on
{person}"; `proposal.approved` `approval_card` "✓ Approved by {person} · {time}"; `return`
`season_stage` (Gather · Prepare · Review · Deliver · Done). W-02-T04, DEC-4602.

## Human-only actions

Plan approve, edit and cancel; answers and skips; proposal approve, reject and Undo; `file.save`.
No agent, system, support or portal principal holds `session.*` or `run_artifact.download`
(W-02-T03, generated security tests).

## Audit events

`workbench_session.created` (blank sessions only), `.renamed`, `.deleted` (titles by hash),
`.context_added`, `.context_removed` (references only); `run_artifact.downloaded`. Outbox:
`workbench_session.created`, `.renamed`, `.deleted`, `.context_changed` (identifiers only).

## Fixtures

E0 fixtures: `apps/web/src/fixtures/seed/workbench.ts` (WB-01 a–g lists and counts, WB-02 picker
tabs and attached context, WB-03 d drill and d2 preview), footed in
`apps/web/src/fixtures/workbench.foot.test.ts`. Consumer tests: W-02-T05.
