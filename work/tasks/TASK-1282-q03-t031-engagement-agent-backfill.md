---
id: TASK-1282
title: Back-fill TASK-050 and TASK-051, the engagement agent v1 (Q-03-T031)
spec: SPEC-027
acceptance_criteria: [AC-1, AC-2, AC-6, AC-7, AC-8]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T031
branch: s9b-independent-suites
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9b-independent-suites (clean session following .claude/skills/ac-test-author/SKILL.md; fake model only, no evals)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Pause stops the next run and every follow-up is sent by a person, never the agent (INV-1, DEC-74)."
TASK-051's AC-3 to AC-5, AC-8 and AC-9 were back-filled on `main` before this row
(`backfill/test_follow_ups_and_due_dates.py`, `backfill/test_due_dates_and_delegation.py`); this
task adds TASK-050's AC-1, AC-2, AC-6 and AC-7 and the INV-1 / DEC-74 half, and re-runs the two
existing suites unchanged.

## Plan (red zone)
- **Files:** `backend/tests/integration/backfill/test_q03t031_engagement_agent.py`; shared helper
  `backend/tests/integration/backfill/q03_agent_support.py` (also used by TASK-1283).
- **Boundary:** `create_app()` over HTTP for what people do (engagement creation, autonomy, pause
  and resume, the feed); the relay's subscribers (`agents.api.SUBSCRIPTIONS`) for events; a
  recording stand-in for the Temporal client; the agent's one activity `handle` per recorded
  signal, as its workflow runs it (TASK-050 design 1). No model at all (SPEC-027 §10).
- **Production:** none expected. A defect found is fixed here when small and local (ED-077,
  ED-078 reserved), else held with `xfail(strict=True, reason="TASK-1282 …")`.
- **No migration, flag, matrix or registry edit.**
- **Rollback:** delete the two test files.

## Results (30 tests, all pass; the two TASK-051 suites re-run unchanged, 39 pass)
- **AC-1:** creating an engagement over HTTP relays `engagement.created` to a signal-with-start of
  `engagement-agent:<tenant>:<engagement>`; with `engagement_agent.enabled` off nothing starts;
  `start_agents` signals each open engagement once (the same event on a re-run, handled once),
  never an archived one; an archived engagement's next event ends the agent and screens nothing.
  (`test_ac1_*`, 4)
- **AC-2:** at Routine P-1 starts one screening per version even when the event is delivered
  twice, fed as `P-1 done`; at Advise it is `skipped` with a reason and nothing starts. (2)
- **AC-6:** a partner's pause shows on `GET …/agent` with its reason, a new version is `skipped`
  and not screened, resume screens it once, a second resume starts nothing (no burst), pause and
  resume are audited with the person (`engagement_agent.paused` / `.resumed`, actor `human`);
  only partner and manager may pause or resume (senior, staff, reviewer 403), a client 403/404,
  another firm 404; the firm switch refuses a practice leader, a partner and a stale MFA (403),
  stops every engagement (`firm_paused_at` in the header), and on `firm.agents_resumed` screens
  what arrived once, twice-relayed without a burst; P-3 records suggestions at Advise and is
  `skipped` while paused. (`test_ac6_*`, 12)
- **AC-7:** a row carries policy, integer version >= 1, outcome, reason, record type and id, and
  no client text; newest first; every staff role, firm administrators and practice leaders read
  it; client roles 403/404, another firm 404, a walled member 403/404; the app role may not
  UPDATE or DELETE `agent_activity`; each automatic action is also one `agent.activity` audit row
  by the platform on the engagement. (`test_ac7_*`, 10)
- **INV-1 / DEC-74:** a Routine tick with an overdue item drafts (`drafted`, `drafted_by_kind
  agent`), emails nothing, writes no `follow_up.sent`; an engagement-agent context holding
  `follow_up.send` in its task scope is refused it by `authorise` (matrix `agent: deny`) while it
  may draft; the database refuses `follow_up.sent` written with an agent actor. (`test_inv1_*`, 3)

## Escaped defects
None found. ED-077 and ED-078 unused (ED-078 unused by TASK-1283 too).

## Spec drift (followed the later decision)
| TASK | AC | The spec says | The current contract says | Superseded by |
|---|---|---|---|---|
| 050 | SPEC-027 §14 | every automatic action audited with actor kind `agent`, policy and version | one `agent.activity` audit row by the system actor on the engagement; policy and version on the feed row | TASK-050 D2 (P-1 to P-3 keep today's authority) |
| 051 | SPEC-027 AC-3, §4.6 | Routine sends reminders; feed outcome `drafted` | the agent drafts at every level and a person sends; feed outcomes `done`, `skipped`, `failed` | DEC-74, DEC-220 |

## Spec gaps (tests accept either answer)
- A client principal on `…/activity` and `…/agent/pause`: 403 (role) or 404; the spec says only
  "clients never see it".
- Deduplication of a twice-delivered event's screening is Temporal's (same workflow id); the
  stand-in client records both starts, so the test asserts one id and one feed row.
- AC-1 continue-as-new, timers and the replay histories stay with `tests/workflows/` and the
  unit suites; AC-10 with `apps/web/src/legacy/spec027agent.test.tsx` (not re-written here).

## Masking branch (s9a-pii-masking)
No overlap: the file uses no evidence content. Run against that branch's code on 2026-10-26:
30 pass.

## Progress log
- 2026-10-26: suite written and run (30 pass; with the two TASK-051 suites, 69 pass); gates on
  the touched files pass (ruff format and check, pyright, lint-imports, banned_patterns,
  error_codes, validate_docs, scope_guards, fresh_mfa). No production change.
