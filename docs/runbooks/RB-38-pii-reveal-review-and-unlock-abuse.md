---
id: RB-38
title: PII reveal review and unlock abuse
owner: builder
alarms: [pii.reveal-volume, evidence.unlock-failures]
last_rehearsed: never
rehearse_by: 2027-03-16
---
# RB-38 · PII reveal review and unlock abuse

| Field | Value |
|---|---|
| Owner | the security desk (N lane), with the firm's security admin |
| Task | P-03-T26 (SHL-08 c and d; ADR-097, ADR-031) |
| Kill switches | `evidence.pii_reveal` (reveal), `evidence.viewer_unlock` (password unlock): off answers 404 and the viewer shows the masked value or "Ask the client" |
| Alarms | `pii.reveal-volume` and `evidence.unlock-failures` (definitions below; wired with the security dashboard, DEC-656) |

## 1. "Who saw this SSN?"

A reveal is a person's act (the table's CHECK: `actor_kind = 'human'`), logged twice: a `pii_reveals` row and an `access_events` row (`pii.revealed`). Values are never logged; the region, version and person are.

1. Find the region: the evidence version and the page region the value sits in (the viewer's region id, or the version's `pii_regions` row for the field).
2. Read the reveals of that region, as the firm's security admin or the platform's on-call through the audit explorer:
   - `pii_reveals` where `region_id` = the region: `user_id`, `reason_code`, `context_ref`, `mfa_at`, `revealed_at`, `expires_at`.
   - `access_events` with kind `pii.revealed` and the same version: who, when, from which request (`trace_id`).
   - Audit events `pii.revealed` and `pii.reveal_throttled` for the version (`GET /v1/audit?target=evidence_version:<id>`).
3. Answer with the people, times and reasons. A reveal without a fresh second factor cannot exist (`mfa_at` is required by the route); an offshore reader cannot reveal (AC9.4).

## 2. Reveal volume alarm (`pii.reveal-volume`)

Fires when one person reveals more than **20 values in an hour** in one firm, or the firm passes **100 in a day**. The route already rate-limits per person (`pii.reveal_throttled`, 429 `tin_reveal_rate_limited` on TINs); the alarm is for a pattern under the limit.

1. Identify the person and the versions (section 1, grouped by `user_id`).
2. Ask the firm's security admin whether the work explains it (an engagement's source review).
3. If not explained: switch `evidence.pii_reveal` off for the firm (`make flag NAME=evidence.pii_reveal FIRM=<code> VALUE=false`), open an incident (`docs/ops/incident-templates.md`), and keep the rows: nothing is deleted.

## 3. Unlock failures alarm (`evidence.unlock-failures`)

Fires when one version has **5 failed unlocks** (`evidence_version.unlock_failed`) or any `evidence_version.unlock_throttled` in an hour. The derivation never stores the password; a failure says only that it did not open.

1. Read the audit events for the version: who tried, how often, from which sessions.
2. One person retrying a client's wrong password: tell the firm to "Ask the client" (state d).
3. Several people or sessions, or a pattern across versions: switch `evidence.viewer_unlock` off for the firm and open an incident.

## 4. Drill (staging)

Twice a year, and before `rehearse_by`: on the Brightwater Hale staging tenant, reveal 21 values as one synthetic person in an hour and fail 5 unlocks on one version; confirm both alarms fire, walk sections 1–3, and record the drill here (`last_rehearsed`).
