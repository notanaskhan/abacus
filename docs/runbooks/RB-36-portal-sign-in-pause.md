---
id: RB-36
title: Pause portal sign-in for a firm
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-03-16
---
# RB-36 · Pause portal sign-in for a firm

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV1 |
| Linked from | RB-22 (identity outage: the portal half); RB-35 (a lockout wave) |
| SLO affected | SLO-01 (sign-in errors) |
| Kill switches that apply | `portal_sign_in` per firm (`platform_control`, ADR-157); the WAF rate rule on the portal distribution |
| Rehearse by | before both portal flags retire (P-08-T28, Tue Mar 16, 2027) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Written for P-08-T28 (P-08-T21 Story 7.3, SPEC-320 AC-20; `docs/contracts/platform-ops.md` §3.7). With a firm's `portal_sign_in` control on, its portal answers 503 `sign_in_paused` to start, verify, resend and the second step, within the controls cache (10 seconds). Sessions already open carry on: refresh and every signed-in route never ask. Staff sign-in is untouched.

## 1. Recognise it
Pause a firm's portal sign-in when any of these holds:
- a credential-stuffing or enumeration wave against one firm's portal host (RB-35 section 4);
- a code email goes to the wrong people or carries the wrong firm's branding;
- a defect lets a sign-in reach the wrong firm or scope (then RB-08 leads, and this is its containment step);
- the firm asks for it while it investigates.

## 2. Contain
As an ops task on the environment (`ops-task.yml`; production through an ops-request PR), never from a laptop:

```
python -m abacus_tools.platform_control set --control portal_sign_in --scope firm \
    --tenant <tenant_id> --on --operator <handle> --reason "RB-36: <ticket>"
```

The change is written to `platform_control_changes` and to the firm's audit trail as `platform_control.changed` by `operator:<handle>`. Wait 10 seconds, then check: a start on the firm's host answers 503 `sign_in_paused`. If every firm is affected, repeat per firm and say so in the incident channel; there is no platform-wide portal switch.

Open sessions are not ended by the pause. If a session itself is the problem (a token reached the wrong person), end it through RB-08's steps.

## 3. Preserve
`platform_control_changes` rows, the audit events around the window (`portal_sign_in.*`, `session.*`), the WAF sampled requests summary. Identifiers only; never an email address or a code.

## 4. Assess
How many sign-ins were refused while paused (503s on `/v1/portal/auth/*` for the host); whether any sign-in succeeded that should not have (RB-08's question); the cause.

## 5. Notify
Tell the firm's admins in-app that client portal sign-in is paused and why in one line; clients already signed in can keep working. The firm tells its clients; the portal never shows "Accrued".

## 6. Recover
1. Fix the cause (a code change through the batch, or a hotfix if production is broken; a WAF rule; a template import).
2. Resume: the same command with `--off` and `--reason "RB-36: resolved <ticket>"`.
3. Clear any locks the wave left on real people (RB-35 section 2).

## 7. Verify
A start on the firm's host answers 202 and a known client completes sign-in (and the second step if covered); `python -m abacus_tools.platform_control list` no longer shows the firm's control.

## 8. Review
Blameless review (ADR-097). If the pause came late, add an alarm on `portal_sign_in.locked` per firm per hour carrying this runbook's URL.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
