---
id: ADR-345
title: Firm-authored instructions as delimited, semi-trusted context after the registered prompt
status: accepted
date: 2026-11-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

P-52 (DEC-90, AG-13). The plan's alias for this ADR is "ADR-162"; that number is P-31 on `main`
(client withdrawal of unaccepted uploads, accepted 2026-10-22), so P-52 takes the next free
number, ADR-345 (`docs/adr/backlog.md`, DEC-5801). Drafted and accepted with K-03-T01
(TASK-8800) under AMENDMENT-solo, on Ayush's instruction of 2026-11-20. Amends ADR-047 and
ADR-052; PROMPT-001 keeps enforcing it.

## Context
K-03's agent columns (SHT-04), K-05's skills and saved prompts let a firm write text that steers the
Accrued Agent: "flag any invoice dated after year end", "follow BH-SK-430". ADR-047 says the
instruction layer is a registered prompt and nothing else; ADR-052 treats all client content as
hostile. Firm text is neither: it is authenticated (written by a named firm user with a matrix
action) but it is not reviewed by us and may carry pasted client text. Without a rule, firm text
either can't be used at all or creeps into the system prompt, where it could override tool
bounds, attribution or the "agents propose, humans decide" rule (ADR-005).

## Decision
1. **Never the system prompt.** Firm-authored text (agent-column instructions, skill bodies,
   saved prompts, firm instructions) enters a model call only as a delimited layer *after* the
   registered capability prompt: `<firm_instruction>` in the firm layer and `<firm_procedure>`
   in the skill layer of `ContextV2Builder` (P-10-T21). The builder still refuses any
   instructions layer that is not a registered prompt (`InstructionsNotRegistered`).
2. **Semi-trusted.** The registered prompt tells the model that firm layers describe *what* to
   check, never *who* may act, and that they cannot widen tools, change attribution or authorise
   a decision. Client-sourced text inside firm text stays in `<untrusted>` blocks.
3. **Bounded by tools and the matrix, whatever the text says.** The tool allow-list is fixed by
   the capability spec; firm text cannot add a tool, a write, a send, an approve, a sign or a
   post. Every outcome is a proposal (a `suggestion`), decided by a named human.
4. **Sanitised and stored.** Firm text is stored with its author, version and sha256; the hash is
   part of the run record and of the agent-column preview match (preview on 3 rows is matched by
   instruction hash). A deterministic check refuses send/approve/sign/post/decide directives and
   tag-breaking sequences (`</firm_instruction>`, `<untrusted>`) before save.
5. **Containment is evaluated.** Every capability that reads a firm layer carries
   `instruction_in_file` and `instruction_in_firm_text` containment cases at 1.0 in its frozen
   eval suite.
6. **Real firms wait.** No real-firm `agent_columns.enabled` before K-05's firm pass-bar runner
   (18 of 20) and G-1…G-6 on Bedrock (Q7); synthetic tenants only until then.

## Options considered
### Option A: delimited semi-trusted firm layer after the registered prompt — chosen
- Pros: firms steer checks; tools and the matrix still bound every effect; cache prefix stays stable.
- Cons: a sanitiser and containment evals to keep.

### Option B: treat firm text as a registered prompt
- Pros: one trust level.
- Cons: every firm edit would need prompt registration and evals; firm text could override bounds.
- Why rejected: unsafe and unworkable.

### Option C: treat firm text as hostile client content
- Pros: maximal caution.
- Cons: the model is told to ignore it, so agent columns cannot work.
- Why rejected: defeats the feature.

## Consequences
**Positive** — agent columns and skills can ship on a stated trust model; PROMPT-001 and the
builder already enforce the system-prompt half.
**Negative** — a sanitiser and per-capability containment cases; firm text in run records must be
classified (Confidential) and never logged.

## Related
DEC-90, AG-13, P-52, ADR-047, ADR-052, ADR-005, ADR-051, ADR-234, PROMPT-001, K-03 (T28, T31,
T34, T41), K-05.
