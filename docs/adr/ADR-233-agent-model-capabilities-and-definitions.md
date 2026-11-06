---
id: ADR-233
title: "Agent model: capability specs in code, firm definitions only narrow them, one principal (amends ADR-046, ADR-047, ADR-048, ADR-057, ADR-061)"
status: proposed
date: 2026-11-06
deciders: ayushkbhatia  # solo edition; acceptance is his (red ADRs never default on silence)
risk_zone: red
proposal: P-22
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by P-10-T58 (TASK-5105), from chapter 05 AG-01 and chapter 03 §7. The plan's
number for this proposal (ADR-157) is a P-ID alias: on `main` that number is another ADR, so
`docs/adr/backlog.md` gives this one.

## Context
ADR-047 requires repo-declared agents. Workbench lets a firm make agents. Both must hold: a firm may
shape what the agent does for it, and nothing a firm writes may widen what the agent can reach.
ADR-057 said no framework until three loop agents justified a harness; the plan now has them.

## Decision
1. **One principal.** There is one agent, attributed "‹person› via Agent" (ADR-005). Definitions are
   configuration of it, not new actors.
2. **Two layers.** *Capability specs* are code (`modules/agents/specs/*.yaml`, ADR-047): shape, tools,
   limits, data classes. *Agent definitions* are firm data: library templates (content), installs and
   firm-made agents. **A definition can only narrow a capability**, never add a tool, a data class,
   a limit or a client scope. Codegen and the service both refuse a widening.
3. **Shapes.** `single_call` (the four live specialists, unchanged), `workflow`, `loop` and
   `conversation`, plus `PolicySpec`. A `loop` must declare `max_tool_calls` and
   `max_repeat_identical_calls`; a spec with a `propose` or `approved_write` tool must declare
   `plan: required_when_writes`; a tool outside `task_scope` fails codegen.
4. **Tools.** Four kinds through the C17 registry: `read`, `compute`, `propose`, `approved_write`. A
   final verb (approve, sign off, release, send, post, export, transmit, decide, publish, adopt,
   resolve, accept, reject) can only be `approved_write`, and its matrix action must be `agent: deny`
   (TOOL-001). There is no generic query tool.
5. **Harness.** A hand-rolled loop inside `agents` on Temporal, with hard limits. ADR-057's trigger is
   met; no agent framework is added (AGENTS 6).
6. **Effective permission** stays the intersection of agent role, initiator and task scope (ADR-025).

## Options considered
### Option A: capabilities in code, definitions narrow — chosen
- Pros: everything reviewable in the repo; a firm's edit can't escalate.
- Cons: a new capability is a deploy.

### Option B: firm-defined agents with their own tool lists
- Why rejected: a firm's data would grant reach; every audit claim about what the agent can do would
  depend on tenant rows.

### Option C: an agent framework
- Why rejected: its loop and tool semantics would sit between us and the admission, boundary and
  budget rules; ADR-019 needs all model calls through `ai_gateway`.

## Consequences
**Positive.** I-AGENT-NEVER holds by construction across firm content.

**Negative.** Specs v2 and codegen grow. The four live v1 specs must load unchanged.

**Follow-ups.** P-10-T10 (C17 stub), T16 to T18 (specs v2), W-03 (definitions).
