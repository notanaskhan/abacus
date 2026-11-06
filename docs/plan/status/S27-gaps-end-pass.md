# S27 gaps end pass (2026-11-06)

The recorded partials in S27's built rows, on main 49922a2fd: DEC-2350, DEC-2352 to DEC-2356.

## Built
| Row | PR | Now live | Still open |
|---|---|---|---|
| T-03-T07 | #1266 | 12 extension, estimate, payment and export routes, the date sweep, the due-soon digest, ack notices | HOME-02's approval row (T-03's cut list), the estimates binder part, sealed list cursors, confirmed-on and contact name on a confirmation, state due dates |
| T-03-T06 | #1270 | Review-point and internal-review effects; staff-edit effects | |
| N-04-T11 | #1271 | Transcript rows; payer citations from the letter's word layer | `NoticeAnalysisWorkflow` (run stays synchronous); 1099 documents have no link to a notice |
| A-06 (SUM) | #1273 | Five misstatement and SUM routes; AUD-09's exception routers | Rows by account, conclusion and sign-off strips, `fs_effect` writers |
| A-04-T31/T35 | #1274 | SOC draft route, exception impact, routing to Findings | |
| A-05-T31/T32 | #1275 | EBP-04 c recalculation; payroll waterfall | Rollovers and the per-FS tie; actual match values; the year's escalation rate |

T-03-T05 is #1269 from another session; this batch's duplicate was closed. `proposed-entries:send-preview` stays a stub: it waits on R-02's C18 template read.

## Found by the tests, fixed
- Writes holding `function_in` authorised at the firm, where the condition fails closed: the shipped approve, mark-filed and flag-likely routes refused everyone.
- PATCH's route guard needs its declared action checked, so flag-likely answered 500 once past authorisation.
- `gate_unmet` facts held a comma list, which `check_facts` refuses: a 500 for a refusal.
- Client wording held amounts and form numbers, which the scope check reads as amounts.
- Issue priority `normal` and waves outside their CHECKs.
- Offshore readers saw extension and estimate amounts with no client consent (review finding).
- AUD-09's exception routers were never registered, so Send to Findings and Convert always answered 503.

## Checks
`make check-fast` passes. Contracts, security, tax, assurance, notices, requests and API unit suites, plus the schema and T-02/T-03 integration suites: 20,059 passed, 3 failed. Two were this batch's pin tests, updated; `test_portal_host_pinning` failed under load and passes alone (8 passed, 1 xfailed).

## Not checked
No full integration shards locally and no web tests. No integration test reaches the SUM routes, the SOC routes, the EBP-04 routes or the notice citation against a real word layer; those have unit tests or none. No staging, no real-model evals, no mutation measure.

## After the rebase on main (2026-11-06)

CI on the first push and a full local unit, contract and security run found more; fixed in this pass:

- `send_due_soon` and `on_filing_acknowledged` emitted with no audit record, so both raised `MissingAuditEvent`. `ExtensionAckRejected.reject_code` was classified restricted, so its emit raised. The due-soon SQL's `date + :days` was ambiguous in Postgres. New tests run all of these through real units of work.
- Firing any answer effect raised, because `Ref` refuses a rule key (on main since T-03-T06). The rule key is now a fingerprint (`rule_fingerprint`).
- `latest_test_of_variant` was added twice (A-05-T23 on main); this stack uses main's.
- Audit targets `audit_misstatement` and `estimate_schedule` are placed; the export and the ack notice use the existing `firm` and `work_item` targets.
- The two classification tests in `tests/unit/kernel/test_classification.py` cannot load `libgobject` on the builder's Mac, so they were not run locally.
