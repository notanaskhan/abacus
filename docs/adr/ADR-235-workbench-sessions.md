---
id: ADR-235
title: "Workbench sessions: a conversation over typed tool plans, every write planned and approved (amends ADR-063)"
status: proposed
date: 2026-11-06
deciders: ayushkbhatia  # solo edition; acceptance is his (red ADRs never default on silence)
risk_zone: red
proposal: P-23
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by P-10-T58 (TASK-5105), from chapter 05 AG-04 and chapter 03 §7. The plan's
number for this proposal (ADR-159) is a P-ID alias: on `main` that number is another ADR, so
`docs/adr/backlog.md` gives this one.

## Context
ADR-063 says the command bar is "not a free-form chatbot". WB-01, WB-03 and the engagement dock need a
thread people can talk to. The risk is a chat box that writes: anything said in a conversation must
not become an action nobody approved.

## Decision
1. **A session is the thread view of one or more runs.** Every run logs into exactly one session;
   engagement runs log into the engagement's dock thread (origin `engagement_run`). Sessions live in
   the `workbench` module; runs in `agents`.
2. **Every write is planned and approved.** A write-proposing turn starts exactly one child run in
   `awaiting_plan_approval`. A plan decision is a new insert-only version, by a human
   (`CHECK (decided_actor_kind = 'human')`).
3. **No decision actions.** A session cannot approve, sign off, release, send, post or decide;
   `file.save` is denied to the agent. Artifacts are firm documents, and stay out of a client's Files
   until a human files them.
4. **The side queue.** With a question open, a new message is answered first and the question stays
   open.
5. **Visibility (DEC-87).** A session whose `client_scope` a viewer cannot open answers
   `locked: true` with no figures; one that read a walled client is omitted. Soft delete keeps items,
   runs and trace. Items are insert-only and schema-versioned.

## Options considered
### Option A: conversation over typed plans — chosen
- Pros: free wording in, typed tools out; approval and audit stay what they are elsewhere.
- Cons: a plan step before any write, on every write.

### Option B: keep the command bar only (ADR-063 as written)
- Why rejected: J11's question to plan to workbook path needs a thread and a plan.

### Option C: a chatbot with direct tool writes
- Why rejected: contradicts ADR-005.

## Consequences
**Positive.** The agent can converse without a new way to write.

**Negative.** Amends `build-plan.md`'s Phase 5 placement; two tables and a session workflow.

**Follow-ups.** P-10-T04 (tables), T43 (session workflow), W-02 (screens).
