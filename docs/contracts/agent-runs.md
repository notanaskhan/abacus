# C6 · Agent runs (v0, live before the v1 contract)

| Field | Value |
|---|---|
| Register row | C6 in `docs/contracts/README.md` |
| Version | v0: live routes that came before the v1 stub (Q-02-T45, P-09-T01) |
| Status | live, pre-contract. v1 extends these routes and does not replace them. |
| Provider epic | P-09. First slice: SPEC-318 (TASK-461, TASK-900, TASK-901). |
| Consumers | WB-09 trace drawer; SHL-13 dock (later); ADM-07 and AUD-29 trace links (later) |
| Freeze sprint | v1 S12 (2027-04-05) |
| Flag | none: read-only over existing runs |
| Spec | `docs/specs/SPEC-318-agent-run-transparency.md` |
| ADRs | ADR-005, ADR-019, ADR-065, ADR-111 |

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
| Run list | `GET /v1/engagements/{engagement_id}/agent-runs?state=active\|recent&limit=` | `agent_run.read` | firm_admin, practice_leader, engagement_partner, manager, senior, staff, reviewer; independence required | denied (no cell) |
| Trace | `GET /v1/agent-runs/{run_id}/trace` | `agent_run.read` | as above, on the run's engagement | denied |
| Trace export | `POST /v1/agent-runs/{run_id}/trace-exports` (201) | `run_trace.export` | engagement_partner, manager, senior; independence and fresh MFA required | agent: deny |

The list filters through `visible()`. The trace and export check the run's engagement with `authorise`.

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
- **TraceExportIn:** `format`, which takes only `json` in v0.
- **TraceExportOut:**
  - `filename`;
  - `content`: `confidential`, the canonical JSON;
  - `sha256`, `rows`, `renderer_version` (`trace-v1`).

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
| 404 | `{"detail": "not found"}` | Unknown run, shadow run, or firm-level run |
| 403 | `{"detail": "forbidden"}` | Not on the engagement, independence unconfirmed, or no recent MFA (export) |
| 422 | validation body | `format` other than `json` |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `agent_run.trace_exported` | Each export | Target `agent_run` id; `Ref(sha256, rows)` |

## 8. Changes v1 will make (P-09)
- Q-02-T45 and P-09-T07 add `GET /v1/agent-runs/{id}` (projection by level, `allowed_actions`) and the `items?after_seq=` feed.
- P-09-T08 splits the trace into `/trace/steps/{id}`, `/trace/records-read` and `/trace/writes`, and adds metadata projection. The single `/trace` response stays as the summary and timeline.
- P-09-T11 adds `pdf` once the C11 renderer and its `run_trace_v1` template exist (S18). JSON keeps this canonical form.
- Once migration 0095 has rows, the trace counts `suggestions` and `proposals` keyed on `agent_run_id`, instead of the lists in `agent_runs.output`.
