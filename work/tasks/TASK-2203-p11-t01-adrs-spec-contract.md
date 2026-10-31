---
id: TASK-2203
title: P-11-T01 ADR-320 (P-19) and ADR-321 (P-32), SPEC-520, C11 skeleton, glossary and task plans
spec: SPEC-520
acceptance_criteria: [AC-29]
risk_zone: amber
status: done
epic: P-11
plan_key: P-11-T01
branch: s17-p11-t01
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-11-01
---

## Objective
Record P-19 and P-32 as accepted ADRs, write SPEC-520 (renderer part), the C11 contract skeleton,
the glossary terms, and the plans of P-11-T02 to T05.

Acceptance: "Both ADRs cite DEC-16, DEC-42, DEC-44, ADR-042 and ADR-110, state the rule-6 position
for Textract, and are accepted before the C11 stub merges."

## Scope
**In**: `docs/adr/ADR-320-deterministic-document-generation.md`, `docs/adr/ADR-321-ocr-and-document-understanding.md`,
`docs/adr/README.md` and `backlog.md` rows; `docs/specs/SPEC-520-p11-document-services.md`;
`docs/contracts/c11-renderer.md` and its README row; glossary (generated document, report template,
DocBlock, render hash, text source); TASK-2204 to TASK-2207 plans.
**Out**: any code (T02 onward).

## Plan
Numbers: the plan's "ADR-152/153" are taken (unauthenticated routes, malware scanning), so P-19 and
P-32 take ADR-320 and ADR-321 from this session's reserved range; recorded in `backlog.md`. SPEC-520
from the reserved SPEC-520+. No migration, registry, flag or protected file. Rollback: revert.
Tests: `make check-fast`'s `validate_docs` (frontmatter, ADR index, spec AC ids, task frontmatter).

1. [x] ADRs (both cite DEC-16, DEC-42, DEC-44, ADR-042, ADR-110; rule-6: Textract is a document
       service, not a model call, with in-code gateway-equivalent checks).
2. [x] SPEC-520 with AC-1..AC-33 (plan F1–F6, F11 and the S17 task rows).
3. [x] C11 skeleton; README row.
4. [x] Glossary.
5. [x] Task files with plans: TASK-2204 (T02), TASK-2205 (T03), TASK-2206 (T04), TASK-2207 (T05).

## Progress log
- `2026-10-29` — Built on `s17-p11-t01` (docs only; validate_docs at the S17 end review).
- 2026-11-01: merged to main in #743 (5923aea71).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| P-19 = ADR-320, P-32 = ADR-321 | the plan's reserved numbers are taken | recorded in backlog.md |
| OQ-4 and OQ-7 take the plan's defaults (SPEC-520 §8) | AGENTS.md "decide, record and carry on" | no |

## Handoff
- **Current state:** PR open, held for the batch. **Next:** P-11-T02 (stacked).
