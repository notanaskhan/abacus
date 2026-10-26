# C6 · Agent runs (v1 in progress; v0 live)

| Field | Value |
|---|---|
| Register row | C6 in `docs/contracts/README.md` |
| Version | v0 live; v1 in progress (TASK-5000): the run read, records read and writes; the run record (TASK-1287) |
| Status | live, pre-contract. v1 extends these routes and does not replace them. |
| Provider epic | P-09, owned by notanaskhan (DEC-336). SPEC-318: TASK-461, TASK-900, TASK-901, TASK-5000. |
| Consumers | WB-09 trace drawer; SHL-13 dock (later); ADM-07 and AUD-29 trace links (later) |
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
| Trace export | `POST /v1/agent-runs/{run_id}/trace-exports` (201) | `run_trace.export` | engagement_partner, manager, senior; independence and fresh MFA required | agent: deny |

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
  - `citations`: `source`, `record`, `locator` (`document`, `claim`, `page`, `cell`), `quote_sha256` and `sheet_sha256` (fingerprints of the words, never the words), and code's `verified`, `reason`, `amount_matches`;
  - `outcome`: `state` (`succeeded`, `needs_input`, `failed`, `cancelled`), `failure_code`, `outputs` (counts by kind);
  - `initiator_user_id`, `started_at`, `completed_at`, `persisted_at`;
  - `record_sha256`: SHA-256 of the canonical JSON of every field above except `persisted_at` (sorted keys, UTC instants). It is the record's own hash, fixed once written; the run view's `run_record_sha256` is a different, read-time fingerprint of the live run row (DEC-396);
  - `projection`: with `metadata` (DEC-87), `records_read` ids are null and citations keep only `source` and code's verdict.

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
- Done in TASK-1287 (Q-02-T41): `GET /v1/agent-runs/{id}/record`. Still to come with C6 v1 (Q-02-T45, P-09): `record_sha256` and `record_persisted_at` on the run summary (ADR-169 §4).
- Still to come: P-09-T07's projection by level; P-09-T08's `/trace/steps/{id}`. The single `/trace` response stays as the summary and timeline.
- P-09-T11 adds `pdf` once the C11 renderer and its `run_trace_v1` template exist (S18). JSON keeps this canonical form.
- Done in TASK-5000: when a run has `suggestions` or `proposals` rows (migration 0095), the trace counts those instead of the lists in `agent_runs.output`, and shows people's decisions on them in the timeline.
