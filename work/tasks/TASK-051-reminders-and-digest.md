---
id: TASK-051
title: "Engagement agent v1, part 2: due dates, overdue reminders, the team digest"
spec: SPEC-027
acceptance_criteria: [AC-3, AC-4, AC-5, AC-8, AC-9, AC-10]
risk_zone: red
status: planned
branch: task-051-reminders
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
The rest of SPEC-027:
- due dates on request items;
- P-4, overdue reminders, sent in the firm's name at Routine or drafted for a person at Advise;
- P-5, the daily team digest;
- the firm's time zone and the agent's daily tick;
- the agent acting under its own `AgentContext`, with the engagement partner as initiator (SPEC-027 Q1, deferred from TASK-050 D2).

## Scope
SPEC-027 AC-3, AC-4, AC-5 (client-facing), AC-8, AC-9, and AC-10 for the new screens.

## Context to load
- Spec: `docs/specs/SPEC-027-engagement-agent-v1.md` (P-4, P-5, Q2–Q6); ADR-005, ADR-025, ADR-061, ADR-062, ADR-090
- Code:
  - `agents/engagement_agent.py` and `engagement_agent_workflow.py` (TASK-050);
  - `agents/spec.py` and `agents/service.py` (`load_agent_context` needs an `agent_runs` row and a spec);
  - `identity/authz/__init__.py` (conditions: `firm_setting(...)` is "not modelled yet", so it denies) and `identity/firm_settings.py` (`autonomy_level`);
  - `communications/service.py` (`send` is for people, during a request), `transport.py`, `invitations.py` (sending in the firm's name);
  - `requests` (models, `request_item.update`), the notifications catalogue;
  - `apps/web`: Board (due dates), Setup, `AgentActivity.tsx`.

## Plan
- [ ] Plan approved by human

### What the code shows
- **The matrix already says agents may send routine reminders** (`follow_up.send`, `agent: firm_setting(autonomy_policy)`), but `authorise` doesn't model `firm_setting(...)`, so it denies.
- **An agent's `AgentContext` needs an `agent_runs` row and a declared spec** (ADR-047). Today's spec format is for model calls: a prompt, tier and output schema are required. The engagement agent makes no model calls.
- **Only communications may send a message** (COMM-001). Its `send` is for a person during a request.
- **Communications doesn't depend on requests or agents.** Agents depends on requests and identity, so it can work out which items are overdue and who to remind.
- **Request items have no due dates.** Firms have no time zone.
- **The TASK-050 workflow has no timer.** A daily tick changes the workflow, so it's versioned (ADR-090) and needs new replay histories.

### Design (for founder review)
1. **Due dates (AC-9; requests migration 0040):**
   - `request_items.due_on` and `request_lists.default_due_on`; an item's due date is its own, else the list's;
   - routes (`request_item.update`): `PUT …/request-items/due-dates` (bulk: item ids and a date, or clear) and `PUT …/request-list/default-due-date`;
   - the Board shows due dates and an "Overdue" pill, with a bulk "Set due date" action;
   - setting or changing a due date signals the agent (`due_dates.changed`), starting it if needed, and restarts those items' reminder sequence.
2. **The firm's time zone:**
   - `firms.time_zone` (IANA name, default `America/New_York`), set on the Autonomy page (`firm.manage_settings`);
   - the tick runs at 09:00 in that zone, on business days (weekends skipped; holidays aren't in v1).
3. **The daily tick (workflow v2, ADR-090):**
   - under `workflow.patched("daily-tick")`, the agent waits for an event or its next tick, whichever comes first;
   - an activity, `engagement_agent.next_tick`, returns the seconds until the next 09:00 business day in the firm's zone (recorded, so replay stays deterministic);
   - the tick runs P-2's daily retrieval, P-4 and P-5 through the same `engagement_agent.handle` (event `agent.tick`);
   - v2 histories are recorded beside v1's, never re-recorded.
4. **The agent's own authority (SPEC-027 Q1, D1):**
   - each tick that may remind creates one `agent_runs` row for a new deterministic spec, `engagement.agent`, with the engagement's earliest-added active partner as initiator;
   - its `AgentContext` comes from the existing `load_agent_context`;
   - the spec registry gains a `shape: policy` variant with no prompt, tier, output schema or evaluation suite; its task scope is `follow_up.draft` and `follow_up.send`;
   - with no active partner, the agent pauses itself (`self_paused_reason: no_partner`), records it in the feed, and the digest's recipients see it.
5. **`firm_setting(autonomy_policy)` in `authorise` (D2, `identity/authz/__init__.py`):**
   - for an agent, the condition allows when the firm's autonomy level is Routine or higher, read fresh, and denies at Advise;
   - the initiator intersection (ADR-025) still applies, so the partner must hold `follow_up.send` (they do), and walls and independence apply to them;
   - no other condition changes.
6. **P-4 Remind (AC-3, AC-4, AC-5):**
   - **who:** items whose due date has passed and whose status is `open` or `needs_revision`, on an open engagement (gate) that isn't paused or archived;
   - **cadence (Q3):** the first reminder on the first business-day tick after the due date, then every 3 business days, at most 3 per item;
   - **to whom:** the item's client assignee, else the engagement's client admins;
   - **batching:** one email per contact per tick, listing their items;
   - **Routine:** sent as the agent, through communications' new `send_reminder` (D3);
   - **Advise:** drafted instead, with the notification `reminders.drafted` to the partner and managers;
   - **stops when:** the item is received, accepted or waived, or its due date changes (the sequence restarts);
   - **records (agents migration 0041):** `reminders` (engagement, recipient, `drafted`/`sent`/`dismissed`, note, sent by, agent run) and `reminder_items` (reminder, item, sequence number). The caps survive restarts.
7. **Sending (D3, communications):**
   - `send_reminder(ctx, engagement_id, recipient_user_id, items)` authorises `follow_up.send` for the caller (a person, or the agent through the intersection), resolves the recipient's email through identity, and renders a fixed template in the firm's name (subject "Whitfield & Lane is still waiting for 3 items for their FY2026 audit of Halvorsen"; item descriptions and a portal link; no evidence content);
   - it sends through the existing transport (local mailbox now, SES with TASK-014) and records the message as invitations do;
   - COMM-001 stays true: only communications sends.
8. **Drafts at Advise (AC-4):**
   - "Reminders waiting for you" on the engagement (Setup, and a count in the header): each draft shows its recipient and items;
   - **send** (optionally edit the note; `follow_up.send`: partner, manager, senior per the matrix);
   - **dismiss** (`follow_up.send`);
   - **list** (`follow_up.draft` holders).
9. **P-5 Team digest (Q6):**
   - each tick with overdue items emits `agent.digest` (engagement, overdue count, reminders sent, drafted);
   - the notifications module delivers it in-app to the partner and managers ("Halvorsen FY2026: 4 items overdue, 3 reminders sent");
   - no email.
10. **Starting every agent (SPEC-027 Q7):** `python -m abacus_tools.engagement_agents start` signals each non-archived engagement's agent once (idempotent; firms with the flag on). The tick then runs daily without waiting for an event.
11. **Tests:**
    - unit: due-date inheritance; the tick time across time zones and weekends; P-4's decision table (cadence, caps, batching, recipients, gate, pause, archive, Advise drafts vs Routine sends); the autonomy condition in `authorise` (Routine allows, Advise denies, the intersection applies); the policy spec; P-5;
    - workflow: the tick under `patched`, offline, and v2 replay histories, with v1's still replaying;
    - integration: reminder records and caps;
    - vitest: due dates on the Board, drafts (send, edit, dismiss), the time zone setting;
    - local smoke: an overdue item reminded once, a second tick within 3 days sends nothing, Advise drafts it, and the email lands in the local mailbox in the firm's name.

**Protected paths (approval file), each named:**
- **`backend/src/abacus/modules/identity/authz/__init__.py`:** modelling `firm_setting(autonomy_policy)` for agents (D2);
- `backend/src/abacus/modules/identity/*` (top-level): the firm time zone, the earliest active partner;
- `backend/src/abacus/modules/agents/**`: the policy spec, P-4, P-5, the tick, workflow v2, drafts routes;
- `backend/src/abacus/modules/evidence/**`: only if the Board's item rows need the due date from evidence (expected: requests only);
- `docs/architecture/permission-matrix.yaml` and the generated `_matrix.py`: only if a new action is needed (expected: none; `follow_up.draft` and `follow_up.send` exist);
- `backend/src/abacus_tools/quality/schema_check.py` and `banned_patterns.py`: new tables and columns, `MODULE_DEPENDENCIES` (agents → communications, D3), LIST-001 entries;
- `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

Not protected but changed: requests, communications, notifications, `abacus_tools`, `apps/web`, the new migrations. Not touched: `api/app.py` (existing routers), the worker.

### Questions for approval
- **D1. Declare the engagement agent as a `shape: policy` spec (no prompt, tier, schema or evaluation suite) so it gets an `agent_runs` row and an `AgentContext` like any agent?** *Recommendation: yes.* It keeps ADR-025's intersection and the audit trail, without pretending it calls a model.
- **D2. Model `firm_setting(autonomy_policy)` in `identity/authz/__init__.py` for agents: allowed at Routine or higher, read fresh?** *Recommendation: yes.* It's the matrix's existing intent for `follow_up.send`. Only that condition, only for agents.
- **D3. Agents depends on communications (a new `MODULE_DEPENDENCIES` edge), which gains `send_reminder`?** Agents works out who and what; communications sends.
  - *Recommendation: yes.* Communications stays the only sender (COMM-001) and doesn't need to know about requests.
  - The reminder records live in agents, beside the cadence that uses them.
- **D4. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-10` — Design written for founder review after TASK-050 merged (#89).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
