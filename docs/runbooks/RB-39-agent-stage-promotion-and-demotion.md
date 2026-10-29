---
id: RB-39
title: Agent stage promotion and demotion
owner: builder
owning_epic: Q-02
alarms: []
last_rehearsed: never
rehearse_by: 2027-04-16
---
# RB-39 · Agent stage promotion and demotion (SPEC-036)

| Field | Value |
|---|---|
| Owner | the founder (operations command; staff use `PUT /v1/platform/agent-stages`) |
| Task | Q-02-T51 (stages Q-02-T07; shadow score and live guard Q-02-T50, DEC-811) |
| Stages | `off` → `shadow` (runs, nothing shown) → `live` (shown to the firm's people, who decide) |
| Kill switch | `make agent-stage … STAGE=off` for one firm and agent; `agents.client_data_optin` off for the firm stops every model call on its data |
| Rehearse by | R2, on a synthetic firm on staging |

An agent moves stage per firm, never platform-wide. Going live needs evidence; going back needs none.

## 1. Promote to shadow
1. The firm has opted in (`agents.client_data_optin`), the provider terms register covers Bedrock today (RB-40), and Bedrock has a passing parity report from the last 90 days.
2. `make agent-stage FIRM=<id> AGENT=<agent id> STAGE=shadow NOTE="<why, one line>"`. Audited as `platform:founder`.

## 2. Promote to live
1. Report: `make agent-stage FIRM=<id> AGENT=<agent id>` (shadow runs against people's decisions). Live is refused below 50 shadow runs over 14 days (SPEC-036 Q1).
2. Score: `make shadow-report FIRM=<id> AGENT=<agent id>` prints `shadow_score.v1` as canonical JSON with its SHA-256. Keep the JSON (vault), record the digest and `as_of`.
3. `make agent-stage FIRM=<id> AGENT=<agent id> STAGE=live NOTE="…" REPORT_SHA=<sha256> REPORT_AS_OF=<as_of>`. Refused unless the recomputed report has the same digest and passes SPEC-036 Q1 and QD-10.
4. Tell the firm's admin; the agent's output now reaches its people, who decide (ADR-005).

## 3. Demote (any time, no evidence needed)
1. `make agent-stage FIRM=<id> AGENT=<agent id> STAGE=shadow` (keep measuring) or `STAGE=off` (stop).
2. Demote at once when: an override rate jumps (`override_rate.v1`), a provider-terms entry lapses (RB-40), an eval suite regresses, or the firm asks.
3. Proposals already shown stay as records; nothing a person decided is undone.

## 4. Verify
`make agent-stage FIRM=<id> AGENT=<agent id>` shows the new stage; the audit trail has the change with the note; for live, the report digest is on the record.

## Rehearsal log
| Date | Where | Who | Result |
|---|---|---|---|
