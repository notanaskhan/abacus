---
id: TASK-414
title: C3 stub PR 2 - proposal, suggestion and decision-card models and 501 routes behind review.grammar_api (P-04-T08)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
epic: P-04
plan_key: P-04-T08
branch: p04-t08-c3-stub-2
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Proposal and decision-card operations exist in the generated client with agent deny on every resolution action and examples that foot (252,200 / 189,150 / 12,610; Feld net change 0)."

## Plan (amber)
- **Files:**
  - `review/contract.py`: decision cards appended;
  - `agents/contract.py`: proposals and suggestions, new;
  - both modules' `api.py`: routers;
  - `docs/contracts/review-grammar.md` part 2.
- **Flag:** `review.grammar_api`, unchanged, from TASK-413.
- **Matrix:**
  - `review.yaml`: the `decision.*` rows;
  - `agents.yaml`: the `proposal.*` rows and `suggestion.resolve`, extended.
- **Migrations:** none.
- **Tests:** none new. The consumer tests are P-04-T09. The generated matrix and introspection tests cover the new actions, and `test_app_gates` lists the new POSTs.
- **Rollback:** revert the commit.

## What changed
- **Decision cards** (`review`), behind `review.grammar_api`: 404 off, 501 on.
  - `GET /v1/decision-cards`, the list envelope, and `GET /v1/decision-cards/{id}`, both `decision.read`.
  - `POST …/{id}/decide` (`decision.decide`).
  - `POST …/{id}/analysis-requests` (`decision.request_analysis`).
  - `POST …/{id}/notify` (`decision.notify`).
  - `POST …/{id}/reassess` (`decision.reassess`).
  - Options are code-computed figures as decimal strings. The agent's recommendation is a tag with agent-text reasons. The rationale is Restricted.
- **Proposals and suggestions** (`agents`, ADR-161), behind the same flag.
  - `GET /v1/proposals/{ref}` (`proposal.read`). `ref` is a UUID or an adapter-prefixed id.
  - `POST /v1/proposals/{id}/approve`, `/reject`, `/route`, `/follow-up` and `/undo`.
  - `POST /v1/suggestions/{id}/adopt` and `/dismiss` (`suggestion.resolve`).
  - Reasoning, row values, totals, the policy note and decisions are Restricted, because they may hold TRI or client figures.
- **Matrix:**
  - New rows: `decision.read`, `decision.decide`, `decision.request_analysis`, `decision.notify`, `decision.reassess`, `proposal.read`, `proposal.approve`, `proposal.reject`, `proposal.route`, `proposal.follow_up`, `proposal.undo`, and `proposal.create` (agent `task_scope` only).
  - `suggestion.resolve` now also has `system: deny` and `independence: required`.
  - Every resolution action is `agent: deny` and `system: deny`.
- **Decisions** (contract §11):
  - the module split (cards in `review`, proposals and suggestions in `agents`) with one flag;
  - `proposal.create` is added now and `decision_card.raise` later with its service;
  - `DecideIn.rationale` is optional on the wire, so the fixed 422 `rationale_required` comes from the service.
  - There is no `AgentTextValue` type in the repo, so agent text is a plain string, documented as agent text.
- **Examples** (contract §8 part 2):
  - Northwind planning materiality: 168,100 and 252,200, PM 189,150, CT 12,610; v3 reassessed at 252,900, a $700 difference, no change;
  - Feld K-1 treatment: four rows, net change 0, tie;
  - the uncited row, AJE-05 over threshold routed to Priya Raman, and reject with Needs client input.
- **Generated files.** `make regenerate` and `make generate` were run.

## Progress log
- 2026-10-22: built per the S3 batch rules, static checks only. ruff, pyright, banned_patterns, validate_docs and `make check-generated` are clean, and the generated matrix and introspection tests for the new actions pass.
  - `test_app_gates::test_ac20_creating_routes_answer_201` still fails on main for `/v1/platform/email-templates/import` (P-01-T05, TASK-401). This task did not cause it.
