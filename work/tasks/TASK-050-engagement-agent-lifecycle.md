---
id: TASK-050
title: "Engagement agent v1, part 1: lifecycle, triggering policies, activity feed, pause"
spec: SPEC-027
acceptance_criteria: [AC-1, AC-2, AC-5, AC-6, AC-7, AC-10]
risk_zone: red
status: in-progress
branch: task-050-engagement-agent
worktree:
created: 2026-10-10
updated: 2026-10-10
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-027, split in two (D1):
- **TASK-050 (this task):** the agent's lifecycle, P-1 (screen), P-2 (retrieve), P-3 (match), the activity feed, and the pause switches;
- **TASK-051:** due dates, P-4 reminders (the agent's own `AgentContext` under the partner, the autonomy condition in `authorise`, Advise drafts), P-5 digest, and the firm time zone.

## Scope
SPEC-027 AC-1, AC-2, AC-5, AC-6, AC-7, AC-10 (for the feed and pause screens), and P-2 and P-3.

## Context to load
- Spec: `docs/specs/SPEC-027-engagement-agent-v1.md`; ADR-058, ADR-059, ADR-060, ADR-062, ADR-063, ADR-090
- Code:
  - `kernel/uow/relay.py` (`OutboxEvent`, at-least-once, 15 s handlers);
  - `kernel/dispatch.py` (`dispatch`, `queue_for`, DISPATCH-001);
  - `worker/__main__.py` (modules, pools);
  - `modules/agents/screenings.py` (`start_screening`, `request_screening`, `SUBSCRIPTIONS`), `agents/workflows.py`;
  - `modules/connections/auto_retrieval.py` (`on_connection_created`, `on_item_classified`, `_run`);
  - `modules/evidence/inbox.py` (`add_to_inbox` emits no event today), `evidence/matching.py`;
  - `kernel/flags.py` and `docs/architecture/feature-flags.yaml`.

## Plan
- [x] Plan approved by human (founder, 2026-10-10: all D-questions, recommendations accepted). Approved by founder: the paths named under *Protected paths*

### What the code shows
- **No long-lived workflows, signals, `continue_as_new` or schedules exist yet.** Every workflow today runs once (screening, embedding, retrieval). This task introduces the pattern.
- **Events reach handlers** through the outbox relay (`SUBSCRIPTIONS`, at least once, 15 s per handler). Handlers start workflows only through `kernel.dispatch.dispatch` (DISPATCH-001), which has no signal call yet.
- **P-1 and P-2 already exist as handlers:**
  - screening on `evidence_version.created` skips at Advise, and its initiator is the person a retrieval ran for;
  - automatic retrieval on `connection.created` / `request_item.classified` checks the flag, autonomy and the gate, then runs as the consenting member.
- **Inbox suggestions are computed on read,** and adding a file emits no event.
- **An agent's `AgentContext` needs an `agent_runs` row with a human initiator.** v1's P-1 to P-3 don't need the agent's own authority: they start work that already runs under a person (D2).

### Design (for founder review)
1. **The workflow:**
   - `EngagementAgent`, ID `engagement-agent:{tenant}:{engagement}`, in the agents module, on the `background` work class;
   - `execution_timeout` none; continue-as-new every 500 handled signals;
   - a `@workflow.signal` `event(name, payload)`, plus `pause`, `resume` and `archived`;
   - it holds no business state: each signal runs one policy activity that reads the current state. That keeps replay safe and the activities idempotent.
   - Versioned from day one under ADR-090 (fixed activity names, plain dataclass inputs), with a replay history committed under `tests/workflows/histories/`.
2. **Starting it, and signals:**
   - `kernel.dispatch` gains `signal_with_start(Workflow, arg, id, signal, payload)`, the only new way to signal (DISPATCH-001 extended);
   - the relay handlers become `on_engagement_event`, which signals the engagement's agent with the event;
   - `engagement.created` starts it, and `engagement.archived` signals it to end;
   - a one-off command starts agents for existing non-archived engagements (SPEC-027 Q7), and is idempotent.
3. **Policies, as activities.** Each reads fresh and checks, in order: the firm pause, the engagement pause, archived, the engagement gate (client-facing only), autonomy, the feature flag. Each writes one feed row.
   - **P-1** (`evidence_version.created`): calls today's screening start (same workflow ID, same initiator rule). Advise or paused means `skipped`.
   - **P-2** (`connection.created`, `request_item.classified`): calls today's automatic retrieval (same checks, same consenting member).
   - **P-3** (new event `inbox_file.added`, emitted by evidence in the same unit of work): computes suggestions with today's `suggest` and records "N suggestions for <file>". It never assigns.
4. **The feature flag** `engagement_agent.enabled` (per firm, default off, expiry 90 days):
   - **on:** the relay routes these events to the agent, and the old direct handlers return early;
   - **off:** exactly today's behaviour.

   Seeded on for Dev firm.
5. **Pause switches (AC-6):**
   - `engagement_agents` (engagement, paused at, by, reason) and `firms.agents_paused_at` / `_by`, read fresh by every policy, so the firm switch needs no fan-out to pause;
   - `POST /v1/engagements/{id}/agent/pause` and `…/resume` (`agent.pause`: partner, manager); `POST /v1/firm/agents/pause` and `…/resume` (`firm_agents.pause`: firm administrator, fresh MFA);
   - **resume** signals the agent(s): one look at the current state. Evidence versions created while paused with no screening run are screened once, and automatic retrieval runs once for the engagement.
   - The paused state shows in the engagement header and on Setup (a checklist line).
6. **The activity feed (AC-7):**
   - `agent_activity` (insert-only): engagement, policy, policy version, action, outcome (`done`, `skipped`, `failed`), reason code, a record link (type and id), and when;
   - `GET /v1/engagements/{id}/activity` (`activity.read`: staff engagement roles, firm administrators, practice leaders; paged, through `visible()`);
   - an **Activity** tab in plain words, with loading, empty, error and not-allowed states.
7. **Data:** migration 0039:
   - agents-owned: `engagement_agents`, `agent_activity`;
   - identity-owned: the `firms` pause columns.

   Schema-check entries for both.
8. **Tests:**
   - Temporal test-server integration: start, signal, pause and resume without a burst, continue-as-new, archive ends it;
   - unit decision tables per policy (paused, Advise, gate, flag);
   - the replay history;
   - feed and pause routes;
   - vitest for the Activity tab and the pause controls;
   - a local smoke on Dev firm with the flag on.

**Protected paths (approval file), each named:**
- `backend/src/abacus/modules/agents/**`: the workflow, policies, feed, pause, routes;
- `backend/src/abacus/modules/connections/**`: P-2 called from the agent; handlers return early under the flag;
- `backend/src/abacus/modules/evidence/**`: emitting `inbox_file.added`;
- `backend/src/abacus/modules/identity/*` (top-level): the firm pause columns and their service;
- `docs/architecture/permission-matrix.yaml` and the generated `backend/src/abacus/modules/identity/authz/_matrix.py`: `activity.read`, `agent.pause`, `firm_agents.pause`;
- `docs/architecture/feature-flags.yaml`: `engagement_agent.enabled`;
- `backend/src/abacus_tools/quality/schema_check.py` and `banned_patterns.py` (DISPATCH-001 for `signal_with_start`, LIST-001 if needed);
- `backend/src/abacus/worker/**`: only if the new workflow needs registering beyond the agents module's `WORKFLOWS`;
- `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

Not touched: `identity/authz/__init__.py` (the autonomy condition is TASK-051), `api/app.py` (existing routers), `ai_gateway`.

### Questions for approval
- **D1. Split SPEC-027 into TASK-050 (lifecycle, P-1 to P-3, feed, pause) and TASK-051 (due dates, reminders, digest, time zone, the autonomy condition)?** *Recommendation: yes.* Each is reviewable, and TASK-050 changes no client-facing behaviour.
- **D2. In TASK-050, P-1 and P-2 keep today's authority** (screening's initiator is the person a retrieval ran for; retrieval runs as the consenting member). The agent's own `AgentContext` under the partner (SPEC-027 Q1) arrives in TASK-051 with reminders, the first action that is the agent's own. *Recommendation: yes.* Moving them to the partner now would change who's checked for walls and independence on work the client already consented to.
- **D3. Gate it behind a per-firm flag, default off, seeded on for Dev firm?** *Recommendation: yes.* Today's behaviour stays the fallback until you turn it on.
- **D4. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-10` — Design written for founder review after SPEC-027 merged (#86).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
