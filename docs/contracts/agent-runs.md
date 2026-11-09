# C6 · Agent runs (v1 frozen; v1.1 additive; v2 frozen)

| Field | Value |
|---|---|
| Register row | C6 in `docs/contracts/README.md` |
| Version | v1 **frozen 2026-10-27** (Q-02-T45, TASK-1423; DEC-595, DEC-596): the run read, records read and writes (TASK-5000), the items feed (TASK-5001), the projections (TASK-5002), the run record (TASK-1287) and the v1 run summary (ADR-169 §4). Snapshot `backend/tests/contracts/c06_agent_runs/v1.json` |
| Status | live, pre-contract. v1 extends these routes and does not replace them. |
| Provider epic | v1: Q-02 (owner change DEC-595, approved 2026-10-27); v2: P-09 and P-10, owned by notanaskhan (DEC-336). SPEC-318: TASK-461, TASK-900, TASK-901, TASK-5000. |
| Consumers | WB-09 trace drawer; SHL-13 dock (later); ADM-07 and AUD-29 trace links (later); G-02 (audit-log run links) and A-01 (archive packaging of run records), consumer tests in `backend/tests/contracts/c06_agent_runs/` |
| Freeze sprint | v1 S12 (2027-04-05) |
| Flag | none: read-only over existing runs |
| Spec | `docs/specs/SPEC-318-agent-run-transparency.md` |
| ADRs | ADR-005, ADR-019, ADR-065, ADR-111, ADR-169 (run records) |

## 1. Purpose
Consumers can list an engagement's agent runs and read one run's trace. The trace covers who started the run, each gateway attempt, what the run proposed, people's decisions on it, and how it finished. Every figure is computed from stored rows. Consumers can also export a trace as canonical JSON with a SHA-256 manifest.

v0 never shows:
- the model id;
- shadow runs;
- confidence figures.

Firm-level runs (no engagement) answer 404 in v0.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Run list | `GET /v1/engagements/{engagement_id}/agent-runs?state=active\|recent&limit=` | `agent_run.read` | firm_admin, security_admin, practice_leader, quality_partner (in scope), engagement_partner, manager, senior, staff, reviewer; independence required | denied (no cell) |
| Run | `GET /v1/agent-runs/{run_id}` | `agent_run.read` | as above, on the run's engagement | denied |
| Trace | `GET /v1/agent-runs/{run_id}/trace` | `agent_run.read` | as above | denied |
| Items | `GET /v1/agent-runs/{run_id}/items?after_seq=` | `agent_run.read` | as above | denied |
| Records read | `GET /v1/agent-runs/{run_id}/trace/records-read` | `agent_run.read` | as above | denied |
| Writes | `GET /v1/agent-runs/{run_id}/trace/writes` | `agent_run.read` | as above | denied |
| Run record | `GET /v1/agent-runs/{run_id}/record` | `agent_run.read` | as above | denied |
| Trace step (v1.1) | `GET /v1/agent-runs/{run_id}/trace/steps/{step_id}?records=5` | `agent_run.read` (content only from P-09-T08) | as above; 404 while `run_trace.enabled` is off, 501 until P-09-T08 | denied |
| Trace export | `POST /v1/agent-runs/{run_id}/trace-exports` (201) | `run_trace.export` | the `agent_run.read` principals (v1.1, DEC-2801); independence and fresh MFA required; the projection is inherited, so firm and security admins export the metadata trace | agent: deny |

The list filters through `visible()`. The trace and export check the run's engagement with `authorise`.

### Content and metadata (DEC-87, TASK-5002)
`agent_run.read` lets a viewer see what ran. Only `run_content.read` lets them see the content. That action covers the engagement's people (partner, manager, senior, staff, reviewer) and practice and quality oversight in scope. It needs independence, and the agent is denied it.

Everyone else gets `projection: "metadata"`. That means security and firm admins without an engagement role.
- **They keep** the summary, timeline kinds, times, states, titles and code details, and records read as sources and counts.
- **They lose:**
  - `model_text`;
  - record references (`target_id` on writes, `ref_id` on items);
  - narration items.

Item seqs are numbered before that filtering, so polling works the same for both projections.

## 3. Models
Code: `backend/src/abacus/modules/agents/runs_routes.py`. Every field is `internal` unless stated otherwise.

- **AgentRunOut:**
  - `id`, `agent` (the agent spec id) and `agent_label`;
  - `state`;
  - `started_at`, `finished_at` and `duration_ms` (computed);
  - `initiator_name`;
  - `subject`: `evidence_version`, `inbox_file`, `template_version` or null. It is a reference kind, never content.
  - v1 (ADR-169 §4, DEC-596): `state_reason` (the queued reason while queued, `escalated` for needs_input, else null); `outcome` (`approved`, `partially_approved` or `rejected`, derived from the decisions on the run's proposals once every non-superseded one is decided, else null); `stage` (`shadow` or `live`); `record_sha256` and `record_persisted_at` (the run record's own hash and write time, null until persisted). The trace-v1 export leaves these out, so its bytes are unchanged.
- **TraceRowOut:**
  - `seq`, `at`;
  - `kind`: start, queued, attempt, output, decision or finish;
  - `title`;
  - `state`: done, failed, waiting or running;
  - `detail`: code words only (outcome or failure codes);
  - `actor`.
- **RunTraceOut:**
  - `run`;
  - `runtime`, `region`, `training`;
  - `attempts`, `tokens_in`, `tokens_out`;
  - `rows`, `records_read` (source and count), `output_counts` (kind and count);
  - `model_text`: `confidential`. It is the run's own words, untrusted, rendered only through AgentText.
- **RunViewOut (v1):**
  - `run`;
  - `run_record_sha256`: SHA-256 of the run row's canonical JSON, which changes whenever the record changes;
  - `allowed_actions`: from `identity.allowed_actions` (every layer except fresh MFA).
- **RunWriteOut (v1):**
  - `kind`: suggestion, proposal or screening;
  - `id`, `target_type`, `target_id`;
  - `key`: a code (the field key, the proposal kind or the screening action);
  - `state`: the row's own status code;
  - `at`;
  - `decision`, `decided_by_name`, `decided_at`: the newest decision.

  No model text appears here.
- **RunItemsOut (v1, TASK-5001):**
  - `run`: the header, which carries the current state;
  - `items`: those after `after_seq`;
  - `last_seq`;
  - `resync`: true when `after_seq` is past the end. The client then replaces its items.
- **RunItemOut:**
  - `seq`, `at`;
  - `kind`:
    - `tool_card`: the legacy run as one card. Its state follows the header.
    - `narration`: an engagement agent action, given as code words (`code` is the action, `state` the outcome, `detail` the reason).
    - `decision`: a person's decision.
    - `failure`: the failure code.
  - `actor`, `ref_type`, `ref_id`.
  - `blocks`: AgentBlocks v1 (TASK-5004), validated by `agents/blocks.validate_blocks`. It is null on pre-v2 runs. The run's fact registry travels with runtime v2 (P-10); until then the client shows a dash for any fact.

  Items are built when read from the run's own records, so nothing is back-filled. Seqs are numbered by time. The client polls every 1.5 s while the run is queued or running and the tab is visible.
- **TraceExportIn:** `format`, which takes only `json` in v0.
- **TraceExportOut:**
  - `filename`;
  - `content`: `confidential`, the canonical JSON;
  - `sha256`, `rows`, `renderer_version` (`trace-v1`).
- **RunRecordOut (v1, TASK-1287; ADR-169 §3):** the run's durable record as stored, written once when the run ended and never changed. Every field is `internal`: identifiers, versions and fingerprints, never prompt text, model text or client content.
  - `run_id`, `engagement_id`, `capability`, `spec_version`, `stage` (`shadow` or `live`);
  - `prompt_ref`, `prompt_sha256`, `model`, `route`, `region` (`local` for the fake route, `us` for the provider's API, the Bedrock region), `terms_version`, `boundary_basis`: from the call whose answer the run kept; null when the run called no model;
  - `input_hashes`: `context` (the run's context hash) and `model_calls` (each call's inputs hash);
  - `records_read`: `type` and `id` of each record the run read;
  - `citations`: `source`, `record`, `locator` (`document`, `claim`, `page`, `cell`), `quote_fingerprint` and `sheet_fingerprint` (`confidential`: HMAC-SHA-256 of the quoted words and the sheet name under the firm's own fingerprint key, never the words; null for a reader who may not read unmasked content, DEC-52), and code's `verified`, `reason`, `amount_matches`;
  - `outcome`: `state` (`succeeded`, `needs_input`, `failed`, `cancelled`), `failure_code`, `outputs` (counts by kind);
  - `initiator_user_id`, `started_at`, `completed_at`, `persisted_at`;
  - `record_sha256`: SHA-256 of the canonical JSON of every stored field except `persisted_at` (sorted keys, UTC instants; citations with their keyed fingerprints). It is the record's own hash, fixed once written; the run view's `run_record_sha256` is a different, read-time fingerprint of the live run row (DEC-396);
  - `projection`: with `metadata` (DEC-87), `records_read` ids are null and citations keep only `source` and code's verdict;
  - `withheld`: entries naming a withdrawn evidence version, left out of this read (P-06-T19). When it is not zero, the shown fields no longer hash to `record_sha256`.

  The model id appears here, unlike on the trace: ADR-169 §4 names this route for consumers that verify or package records (A-07, G-02).

Canonical JSON uses sorted keys, UTC ISO instants and rows in `seq` order. The same trace always gives the same bytes.

## 4. Status words
Run state maps from `agent_runs.status`, the same map P-10-T14 plans:

| `agent_runs.status` | Run state |
|---|---|
| running | `running`, or `queued` while `queued_reason` is set |
| completed | `succeeded` |
| escalated | `needs_input` |
| failed | `failed` |

The UI labels are Queued, Running, Finished, Needs a person and Failed. Trace-row states use the `done`, `failed`, `waiting` and `running` codes.

## 5. Human-only actions
None are decided here; v0 is read-only. Only a person may export; the matrix denies `run_trace.export` to the agent.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | Unknown run, shadow run, or firm-level run; on `/record`, also a run whose record is not persisted yet |
| 403 | `{"detail": "forbidden"}` | Not on the engagement, independence unconfirmed, or no recent MFA (export) |
| 422 | validation body | `format` other than `json` |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `agent_run.trace_exported` | Each export | Target `agent_run` id; `Ref(sha256, rows)` |
| `agent_run_record.persisted` | Once per run, when its workflow persists the record (actor system) | Target `agent_run` id; `Ref(record_sha256)` |

## 8. Changes v1 will make (P-09)
- Done in TASK-5000: `GET /v1/agent-runs/{id}` (with `run_record_sha256` and `allowed_actions`), `/trace/records-read` and `/trace/writes`.
- Done in TASK-5001: the `items?after_seq=` feed, with the read-time legacy adapter (P-09 Story 8.1).
- Done in TASK-5002: the content and metadata projections (DEC-87).
- Done in TASK-1287 (Q-02-T41): `GET /v1/agent-runs/{id}/record`. Done in TASK-1423 (Q-02-T45): `state_reason`, `outcome`, `stage`, `record_sha256` and `record_persisted_at` on the run summary (ADR-169 §4); v1 frozen 2026-10-27.
- v1.1 (P-09-T01, §10): the shapes for P-09-T07's projection by level and P-09-T08's `/trace/steps/{id}` are in; the handlers fill them in S32. The single `/trace` response stays as the summary and timeline.
- P-09-T11 adds `pdf` once the C11 renderer and its `run_trace_v1` template exist (S18). JSON keeps this canonical form.
- Done in TASK-5000: when a run has `suggestions` or `proposals` rows (migration 0095), the trace counts those instead of the lists in `agent_runs.output`, and shows people's decisions on them in the timeline.

## 9. v2 (P-10-T09 stub, 2026-11-06; DEC-2408; frozen 2026-11-08, P-10-T16, DEC-2713)
**One owner per route.** P-09 owns the run view, items feed, engagement run list, trace and trace
export. P-10 owns the streams, run commands and sessions below. `GET /v1/agent-runs/{id}` gains
`RunV2Out`'s fields with P-10-T29. Code: `agents/runs_v2_contract.py`,
`workbench/sessions_contract.py`, `notifications/events_contract.py`, `platform/usage_contract.py`.

Every route answers its matrix action, then 501 until the task named. Flags `agent_runtime.v2`,
`realtime.sse` and `engagement_run.enabled` arrive on the Thu Jan 27, 2028 train; then 404 off.

| Operation | Method and path | Matrix action | Task |
|---|---|---|---|
| Run stream | `GET /v1/agent-runs/{id}/events` (SSE) | `agent_run.read` | T26 |
| Start engagement run | `POST /v1/engagements/{id}/runs` (202) | `agent_run.start` | T39 |
| Plan decision | `POST /v1/agent-runs/{id}/plan/approve`, `/edit`, `/cancel` | `agent_run.approve_plan` | T33 |
| Question | `POST …/questions/{qid}/answer`, `/skip` | `agent_run.answer` | T33 |
| Control | `POST …/messages`, `…/steps/{sid}/retry`, `…/stop` (202) | `agent_run.control` | T33 |
| Sign-off | `POST …/sign-off` | `agent_run.sign_off` | T33 |
| Feedback | `POST /v1/agent-feedback` | `agent_feedback.create` | T33 |
| Auto mode | `PUT /v1/engagements/{id}/auto-mode` | `engagement_ai.configure` | T39 |
| Session | `GET /v1/workbench/sessions/{id}`; `POST …/messages` (202) | `session.read`, `session.create` | T43 |
| Session stream | `GET /v1/workbench/sessions/{id}/events` (SSE) | `session.read` | T26 |
| Badge stream | `GET /v1/me/agent-events` (SSE) | `session.read` | T26 |
| Invalidations | `GET /v1/events?topics=` (SSE); `POST /v1/events/{stream_id}/topics` | `events.subscribe` | T27 |
| Capabilities | `GET /v1/agents/capabilities?engagement_id=` | `session.read` | T45 |
| Firm usage | `GET /v1/firm/usage?month=` | `usage.read` | T42 |
| Engagement effort | `GET /v1/engagements/{id}/effort` | `engagement.read` | T42 |

**Events** (`RunEventOut`): `run.state`, `step.state`, `item.appended`, `item.patched`,
`plan.proposed`, `plan.decided`, `question.opened`, `question.answered`, `proposal.created`,
`proposal.decided`, `decision.requested`, `decision.decided`, `artifact.ready`, `resync`, `locked`,
and a `:hb` heartbeat. `seq` is per run or per session; `Last-Event-ID` is scoped to the stream.
Identifiers, enums and verified items only; an item holding a Restricted field travels as
`{id, ref_only: true}`; over 64 KB by reference. **No model token is ever streamed** (ADR-234).

**Examples.**
- **Run #4118**, Season Progress Reporter, Sep 14: `succeeded`; records read 2,625 = 224 + 214 + 241 +
  1,946; 79 citations; 2 m 41 s.
- **Run #4127**, Northwind engagement run: 14 workpapers = 1 + 5 + 1 + 4 + 3 over 5 levels; plan
  approved 9:24; TB 9:26; `blocked_on_decision` on materiality at 9:27 with `blocked_on.role`
  `engagement_partner`; IC failed 9:58 (BH-EBP-140 step 8); decided 11:12.

Both validate against the schemas in `backend/tests/contracts/c06_v2/test_c06_v2_stub.py`.

### 9.1 Freeze (P-10-T16)

**Snapshot.** `backend/tests/contracts/c06_v2/v2.json` holds the OpenAPI schemas of every v2 model a
route exchanges (`python -m abacus_tools.contracts --freeze c06_v2 v2`; `--check` runs in the
contract tests). Additions pass; a removed or retyped field, a field made required or a removed
enum member fails unless it ships as v3 with a sprint of overlap, never inside the Jan 1 to Apr 20
window. `RunEventOut`, `RunStepV2Out` and `InvalidationEventOut` travel on SSE streams outside
OpenAPI; `c06_v2/test_c06_v2_stub.py` pins their shapes.

**Callers.**

| Caller | Reads | Writes |
|---|---|---|
| P-09 dock (SHL-13), AUD/TAX/CLS docks | run view, items, run stream | plan decision, answer, control, sign-off, feedback |
| Workbench (WB-03, WB-09) | session snapshot, session stream, capabilities | session messages |
| Today and Home badges | badge stream | none |
| ENG-12, engagement cockpits | engagement runs, effort | start engagement run, auto mode |
| ADM usage (ADM-14) | firm usage | none |
| Any screen holding a cached list | invalidations | stream topics |

**Status words.** Run states are the registry's 14 (`docs/product/status-vocabulary.yaml`,
`agent_run`): queued, planning, awaiting plan approval, dispatched, running, needs input, blocked on
decision, waiting on inputs, succeeded ("Ready for review"), approved, partially approved, rejected,
failed, cancelled. Step, session and question states are the registry's `agent_run_step`,
`workbench_session` and `agent_question`. The legacy words `completed` and `escalated` read as
`succeeded` and `needs_input` with reason `escalated` (0680's sync; 0711's backfill).

**Human-only actions.** Plan approve and edit (`agent_run.approve_plan`), run sign-off
(`agent_run.sign_off`) and proposal decisions are a live person's, refused to agent and system
principals at the matrix and by the database (`agent_plans_decision_is_human`,
`run_sign_offs_human`, both bound to the session's actor). Answering a question and stopping a run
are a person's commands; the agent never answers its own question.

**Audit events.** `agent_run.started`, `agent_run.plan_decided`, `agent_run.question_answered`,
`agent_run.stopped`, `agent_run.signed_off`, `agent_feedback.created`, `engagement_ai.auto_mode_set`,
`session.message_posted`, one `model.called` per attempt (`converse()` included, ADR-234) and
`agent_runs.backfilled` per backfill batch (P-10-T14). Outbox events carry identifiers only.

## 10. v1.1 (P-09-T01, 2026-11-08; TASK-6201; DEC-2801)
Additive to v1: no field is removed or retyped, so v1's snapshot still passes and no new version
is cut (handshake rule 5). Every new field is optional, null or empty until its handler task fills
it. Code: `backend/src/abacus/modules/agents/runs_routes.py`.

**New shapes.**
- `RunViewOut`: `header` (`RunHeaderOut`: `run_number`, `blocked_on`, code's `counters`,
  `runs_as_name`, `trigger_kind`, `work_item_ref`), `levels` (`RunProjectionLevelOut`: `level`,
  `total`, `done`, `running`, `blocked`, `waiting`, `queued`, `failed`; computed, never stored) and
  `access` (`content` or `metadata`, the same value as `projection`).
- `RunItemsOut`: `next_seq` (the `after_seq` cursor). `RunItemOut.session_kind`: the v2 wire set
  (`user`, `line`, `block`, `tool`, `progress`, `question`, `answer`, `error`, `plan`, `approval`,
  `decision_ref`, `artifact`, `run_card`, `notice`); a legacy item maps `tool_card` → `tool`,
  `narration` → `line`, `decision` → `decision_ref`, `failure` → `error`.
- `RunTraceOut`: `summary` (`TraceSummaryOut`, WB-09's card: run number, agent, start, trigger,
  runs as, duration, records read, citations, writes done and waiting) and `access`.
  `TraceRowOut`: `phase` (`plan`, `execute`, `compute`, `proposed_write`, `decision`, `policy`,
  `steer`, `notice`), `mark` (`start`, `plan`, `done`, `running`, `waiting`, `blocked`, `failed`,
  `muted`) and `duration_ms`.
- `RecordsReadOut`: `connection_id` and `through` (WB-09's "Through": the firm connection, or null
  for Accrued's own records). `RunWriteOut`: `state` (`waiting`, `approved`, `declined`,
  `superseded`), `approver_name`, `proposal_id`.
- `TraceStepOut` on the new step route: `step_id`, `title`, `args_summary`, `records_read` and up
  to five `samples` (`record_type`, `id`, `label`, `open_route`), filtered by `visible()`.

**Flags.** `agent_dock.enabled` (SHL-13) and `run_trace.enabled` (WB-09 v1.1 and the step route),
boolean, default off, owner notanaskhan, expiring 2027-05-07 (DEC-137's 180 days; the plan's
2028 dates are calendar dates).

**Route ownership** (one owner per route; P-10 adds fields to P-09's handlers, never a route):

| Route | Created | Owner from S31 | Extended by |
|---|---|---|---|
| `GET /v1/engagements/{id}/agent-runs` | Q-02-T45 (S12) | P-09 | — |
| `GET /v1/agent-runs/{id}` | Q-02-T45 / TASK-5000 | P-09 (T07) | P-10-T29 (v2 fields) |
| `GET /v1/agent-runs/{id}/items?after_seq=` | TASK-5001 | P-09 (T07) | P-10-T29 |
| `GET /v1/agent-runs/{id}/trace` | TASK-461 | P-09 (T08) | P-10-T44 (durable v2 records) |
| `GET /v1/agent-runs/{id}/trace/steps/{step_id}` | P-09-T01 (v1.1) | P-09 (T08) | P-10-T44 |
| `GET /v1/agent-runs/{id}/trace/records-read` | TASK-5000 | P-09 (T08) | — |
| `GET /v1/agent-runs/{id}/trace/writes` | TASK-5000 | P-09 (T08) | — |
| `GET /v1/agent-runs/{id}/record` | Q-02-T41 | Q-02 | — |
| `POST /v1/agent-runs/{id}/trace-exports` | TASK-461 | P-09 (T11; the only trace export) | P-10-T44 |

P-10 builds no second run list, no `GET …/trace.json` and no `GET …/trace.pdf`.

**C6 v2 field request (to P-10).** `RunStepV2Out` (and `agent_run_steps`) gains `sample_refs` (at
most five `{record_type, id}`) and `source_ref` (the connection id, or `accrued`), both nullable.
They feed `TraceStepOut.samples` and `RecordsReadOut.through`. Additive to the frozen v2 snapshot,
so they ride an expand-only migration (P-09 §4.2's fallback) if P-10's Dec 24 schema lacks them;
until then the step detail shows the argument summary without samples.

**Fixtures.** E0 runs in the web fixtures (`apps/web/src/fixtures/seed/agent-runs.ts`): #4118
Season Progress Reporter (Sep 14, 9:00 AM, 2,625 records, 79 citations, 1 write waiting), #4127
the Northwind PY2025 planning run (Sep 14, 9:24 AM, running, materiality blocked on a partner
decision), the Aug 17 failed run (CCH Axcess Tax 401) and Copperleaf Run 2.


## 11. Run read model (P-09-T07, 2026-11-09; TASK-6304; DEC-3004)
Fills §10's run-view and feed fields; additive (one enum widened), so v1's snapshot still passes.
Code: `agents/run_views.py`, `agents/runs.py`, `agents/run_recorder.py`.

- **Header** from the v2 columns: `run_number`, `blocked_on` (a metadata reader gets its `kind`
  and `role` only), `counters` (v2 runs), `runs_as_name`, `trigger_kind`, `work_item_ref` (null for
  metadata).
- **Levels**: the newest decided plan version's steps (`key`, `level`), each counted in its latest
  step row's bucket: `succeeded`/`skipped` done, `running`/`dispatched` running, `blocked`,
  `waiting_on_inputs` waiting, `queued` (and a plan step with no row yet), `failed`/`cancelled`
  failed. Levels below 1 count as level 1. A legacy run has none.
- **`allowed_actions`** passes through the caller's allowed set of `agent_run.read`,
  `run_trace.export`, `agent_run.approve_plan`, `.answer`, `.control` and `.sign_off`; the commands
  are P-10's routes (P-09-T14 binds them).
- **Items**: a v2 run (a plan or runtime steps) reads its `item.appended` run events in `run_seq`
  order, 200 at most per page; `RunItemOut.kind` widens to the v2 wire set and `session_kind` is
  the same value; stored `blocks` are validated as AgentBlocks again or dropped. A metadata reader
  gets no `line`, `block`, `user`, `answer` or `question` items and no detail, blocks or
  references. A legacy run keeps the read-time adapter (one tool card, templated narration).
- **Engagement list `state=active`**: a v2 run until its state is terminal; a legacy one while it
  runs.
- **Synthetic-only recorder**: `record_synthetic_run(tenant, RecordedRun)` writes a v2 run (row,
  one approved plan, step rows, item events, counters) for a synthetic firm only (`synthetic_only`
  otherwise), as the run's initiator, with `agent_run.recorded_synthetic`. P-09-T12's scenario
  calls it; P-10-T25's harness records real runs.

## 12. Trace read model (P-09-T08, 2026-11-09; TASK-6305; DEC-3005)
Fills §10's trace fields; additive (`TraceRowOut.kind` gains `plan` and `step`). Code:
`agents/trace.py`, `agents/runs.py`; migration 0751.

- **Summary** on every trace (`TraceSummaryOut`): run number, agent label, start, trigger, runs
  as, duration, records read, citations, writes done and waiting (code's counts).
- **v2 timeline** from durable records (survives the 30-day `run_events` prune): the plan decision
  (`kind: plan`, actor the decider) and each step row (`kind: step`). Phase by step kind (`tool`
  execute, `compute` compute, `approval` proposed_write, `decision` decision, `question` steer,
  else notice); mark by state (`succeeded` done, `running`/`dispatched` running,
  `waiting_on_inputs` waiting, `blocked`, `failed`/`cancelled` failed, `queued`/`skipped` muted);
  title "‹Verb› › ‹plan label›"; detail a code (needs, error code, blocked-on role). Legacy rows
  gain a phase and mark too.
- **Metadata projection**: titles are the verb alone, no details, no model text.
- **Step detail** `GET …/trace/steps/{step_id}?records=` (no longer 501): 404 with the flag off,
  for a metadata reader, or for another run's step; otherwise the step's title, the harness's
  redacted `args_summary` (TINs scrubbed) and up to five samples resolved by the owning module's
  `agents.trace.register_trace_samples(record_type, resolver)`, filtered by `visible()`; a type
  without a resolver shows none.
- **Records read** for a v2 run: steps' `records_read` summed by the tool's declared record type
  and `source_ref`; `through` is "Accrued" for the firm's own records, the connection id otherwise.
- **Writes**: `state` (`waiting`, `approved`, `declined`, `superseded`), `proposal_id`, and
  `approver_name` for a waiting proposal (its `routed_to_user_id`); none for metadata readers.
- **Region** from the register entry covering the run's route on its start day; training from
  the register's statement. Model text has TINs scrubbed.
- **Migration 0751** (P-09 §4.2 fallback): `agent_run_steps.sample_refs` (≤ 5 `{record_type, id}`)
  and `source_ref` (`accrued` or a connection id), nullable, app-updatable; the harness fills them.
- The trace-v1 export's bytes are unchanged: the v1.1 fields stay out of `canonical` until
  P-09-T11's export.
