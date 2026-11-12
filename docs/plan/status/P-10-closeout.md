# P-10 close-out: agent runtime v2 and real time (P-10-T56, 2026-11-12)

P-10 (SPEC-647) is built: 58 rows, every one with a task file; 50 done, 7 partial, 1 deferred
(`docs/product/capacity-ledger.md`, DEC-4414). What it gives other epics:
`docs/contracts/p10-consumer-notes.md`. How to add to it: `docs/architecture/reference/ai-agent.md`
("Runtime v2"). Register: C6 v2 frozen and live, C17 v1 frozen and live (`docs/contracts/README.md`).

## Flags
`agent_runtime.v2`, `realtime.sse`, `engagement_run.enabled`: all per firm, default off, expiring
2027-05-07, each naming J11 and J23 as its flip journeys. Renewal calendar:
`docs/plan/status/flag-renewals-2027.md` ("The P-10 runtime v2 flags"): every train until the Tue
Apr 25, 2028 renewal past M17. The flip: `docs/runbooks/runtime-v2-flip.md` (Tue May 2, 2028).

## Left open (each in its task file)
| Row | What is left | Needs |
|---|---|---|
| P-10-T13 | Committed Bedrock and refreshed direct parity reports; no real route takes a loop spec until then | The evaluation account |
| P-10-T14 | The legacy run backfill on production-sized data; deploy-pipeline wiring | Staging/production |
| P-10-T15 | The SSE edge Terraform applied; RB-65's stream verification | Staging apply |
| P-10-T46 | Real `runtime.conformance` runs on both routes | The evaluation account |
| P-10-T50 | The run-stream Playwright specs on staging; J11 b2–b3 (`test.fixme` until W-02's WB-01 g) | Staging; W-02 |
| P-10-T51 | The 1,500-stream load run and its report; RB-28 rehearsed; 250 `loadtest-stream-*` staff on PF-X1; whether staging's `db.t4g.micro` must grow | Staging |
| P-10-T54 | The flip rehearsal, the 14-day shadow of engagement runs and the canary from Mon Mar 20, 2028; both founders' approvals | Staging; both founders |
| P-10-T53 | The delta pen test | Deferred (DEC-1389) |

## Hand-off notes
- **Planning materiality in the engagement run** (DEC-4416): the step fails closed until
  assurance registers a run step that raises the card through `propose`; J23's blocking step is a
  strict xfail naming it.
- **Adapter kinds** (DEC-4415): K-1 treatment and residency approvals apply after commit from
  the `proposal.decided` subscriber; their Undo is refused (`effect_started`).
- **The `session:` topic** is registered by the workbench (`session_events.py`, TASK-7325):
  a session's items reach its thread live.
- **`presence:{object_ref}`** is reserved for K-03.
- **The PDF trace export's v2 fields** (cut 3) go to A-07 or G-02.
- **Statement budgets** for the run reads (P-10-T52) are measured at the S38 end pass and
  recorded in `test_p10t52_run_read_queries.py`.
- **Threat model:** TU-01 to TU-09 (`docs/architecture/ai-threat-model.md`); a new tool copies the
  update checklist into its PR.
