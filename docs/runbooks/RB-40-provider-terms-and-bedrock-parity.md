---
id: RB-40
title: Provider-terms review_by renewal and Bedrock parity refresh
owner: builder
owning_epic: Q-02
alarms: []
last_rehearsed: never
rehearse_by: 2027-04-16
---
# RB-40 · Provider-terms renewal and Bedrock parity refresh

| Field | Value |
|---|---|
| Owner | the founder (the register is PROTECTED: only the founder edits it) |
| Task | Q-02-T51 (register ADR-114; parity SPEC-010 Q2) |
| Fails closed | a model call on client data needs an entry covering Bedrock today (`approved_on ≤ today ≤ review_by`) **and** a passing parity report from the last 90 days; either missing, the gateway refuses real-firm calls (synthetic firms keep working) |
| Kill switch | none needed: lapse is itself the stop |
| Rehearse by | R2 |

## 1. Provider-terms renewal (before `review_by`)
1. Thirty days before an entry's `review_by`, read the provider's current terms, DPA and sub-processor list.
2. Counsel reviews first (`second_approver: counsel`, `second_approved_on`).
3. Add a **new** entry to `docs/operations/provider-terms.yaml` (never edit an old one): the documents with versions and acceptance dates, training `none`, retention, region `us-east-1`, sub-processors, breach notice, `approved_by: founder`, `approved_on`, `review_by` at most 12 months later.
4. `python -m abacus_tools.codegen.provider_terms` (or `make regenerate`), commit both files in one PR; a test fails if they differ.
5. If the date passes first: real-firm calls stop on their own. Demote live agents to shadow for the gap (RB-39) so people are not waiting on proposals that never come, and tell the firms.

## 2. Bedrock parity refresh (every 90 days)
1. With real Bedrock credentials (vault), on staging: `make route-parity ROUTE=bedrock`. It writes `docs/operations/route-parity/bedrock-<date>.json` and prints its SHA-256; it exits non-zero on a failing route.
2. Commit the report; set the deployment's `route_parity.bedrock` to `{checked_on, sha256}` (configuration, not code) in the same window.
3. A failing report: do not record it; keep real-firm calls on the previous report until it ages out, open a SEV3, and demote live agents before the 90 days end.

## 3. Verify
The gateway's readiness check for a real opted-in firm passes (provider terms covered today, parity under 90 days); `make flag-calendar` and this runbook's next dates are in the ops calendar.

## Rehearsal log
| Date | Where | Who | Result |
|---|---|---|---|
