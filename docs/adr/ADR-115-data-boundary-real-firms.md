---
id: ADR-115
title: AI sees a real firm's data only through SPEC-036's five conditions, enforced in the gateway
status: accepted
date: 2026-10-16
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-112 kept every real model on synthetic firms until provider terms were recorded, staging existed and a spec defined how to lift it. ADR-114 records the terms; SPEC-036 (approved 2026-10-16) defines the lift.

## Decision
- **A synthetic firm** (`firms.synthetic`, set only by seeding and evaluation runs) may use any enabled real route, as before.
- **Any other firm** reaches a real model only when every one of these holds, checked in the AI gateway before any network call:
  1. the route is `bedrock` and settings say `model_data_boundary: client_data` (staging and production only);
  2. the provider terms register covers the route today (ADR-114);
  3. a firm admin has opted the firm in, against the current disclosure;
  4. the agent's spec says `client_data: cleared`, which needs a committed passing Bedrock evaluation and Bedrock route parity;
  5. the engagement isn't excluded by its partner, and the agent's stage for the firm is `shadow` or `live`.
- **A refusal** names the first failing condition, is audited and counted, and is never retried or rerouted. A real firm's call never fails over to `direct` (ADR-113).
- **Each usage record** keeps its basis (`synthetic` or `client_data`) and, for client data, the register version.
- **Model-written text to a real firm's clients** stays off (ADR-111); this ADR doesn't change it.

## Consequences
Until the register holds a Bedrock entry, an agent is cleared and TASK-076 adds opt-in, exclusion and stages, every real firm is still refused. The difference from ADR-112 is that the path to lifting is now defined and checked by code.

## Related
Supersedes ADR-112. ADR-031, ADR-111, ADR-113, ADR-114; SPEC-026, SPEC-036.
