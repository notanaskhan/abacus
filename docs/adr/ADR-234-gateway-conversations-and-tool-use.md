---
id: ADR-234
title: "Gateway conversations and tool use: ai_gateway.converse() beside call(), no token streaming to browsers (amends ADR-019, ADR-049, ADR-051, ADR-055)"
status: proposed
date: 2026-11-06
deciders: ayushkbhatia  # solo edition; acceptance is his (red ADRs never default on silence)
risk_zone: red
proposal: P-46
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by P-10-T58 (TASK-5105), from chapter 05 AG-02 and chapter 03 §7. The plan's
number for this proposal (ADR-158) is a P-ID alias: on `main` that number is another ADR, so
`docs/adr/backlog.md` gives this one.

## Context
`ModelRequest` is a single system-and-user turn. A plan-then-act agent needs multi-turn tool use. The
live screener, upload reviewer and matcher run on `call()` during the 2028 window and must not move.

## Decision
1. **Additive.** `ai_gateway.converse()` is a new path beside `call()`. `call()` is untouched; the
   existing suites stay byte-identical (AC-G6).
2. **Same invariants per attempt.** Registered prompt, output schema, tier, budget, tenant, admission,
   data boundary and route parity. §7216 refusal `consent_7216` comes before any provider call and
   never reroutes (ADR-115). The platform AI pause stops any turn within 10 seconds (ADR-097).
3. **Exactly one record per attempt.** One `usage_records` row (with `step_id`, `session_id`) and one
   `model.called` audit event, each in its own unit of work; inputs logged by hash only.
4. **Tool descriptions are registry prompts**, versioned and hashed as prompts are. A `tool_use` whose
   arguments fail the tool's input schema executes nothing: repaired once, then escalated, then the
   run goes to `needs_input` with reason `escalated`.
5. **Context layer order is fixed for caching:** instructions, tools, firm, engagement, examples,
   then the task and turns. Client content enters in `<untrusted>` blocks (ADR-052).
6. **No token streaming to browsers, on any surface.** Items reach a browser only after schema
   validation and citation verification, over ADR P-15's transport.
7. **Provider seam.** Direct and Bedrock behind one route interface, gated by route parity; a mode is
   cleared per route from signed eval reports.

## Options considered
### Option A: a new `converse()` — chosen
- Pros: nothing live moves in the window; invariants tested on a fresh surface.
- Cons: two call paths until the specialists move.

### Option B: extend `call()` with turns and tools
- Why rejected: an edit to the live path inside the freeze; breaks AC-G6's byte-identical promise.

### Option C: stream tokens to the dock
- Why rejected: unverified text and numbers on screen; ADR-050, ADR-065 and citation verification
  all run on a finished turn.

## Consequences
**Positive.** A run can resume, repair and budget per attempt under existing governance.

**Negative.** No typing effect in the dock; narration arrives by verified item.

**Follow-ups.** P-10-T12, T13 (providers, parity), T19 onward.
