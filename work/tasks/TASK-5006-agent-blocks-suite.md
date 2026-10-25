---
id: TASK-5006
title: "AgentBlocks conformance suite: adversarial corpus, 1.0 on every repeat, seeded regressions"
spec: SPEC-318
acceptance_criteria: [AC-11]
risk_zone: red
status: done
branch: task-5006-blocks-evals
worktree: agentwt
created: 2026-10-26
updated: 2026-10-26
---

## Plan keys
P-09-T15 (partial: corpus and gate; runner store and HMAC report still to come).

## Plan
- **`evals/agent_blocks/suite.yaml`:** 39 cases across DE-3, DE-5, DE-6, references and shape, all deterministic.
- **`tests/unit/agents/test_blocks_suite.py`:**
  - each case through `run_output_check("agent_blocks", ...)`;
  - the score must be 1.0 over 3 repeats;
  - neutralising any one of the eight lint rules must fail the suite.
- **`blocks.py`:**
  - `_DECEPTIVE` refuses bidi controls, zero-width characters, BOM and soft hyphen;
  - `_LINKISH` refuses anything containing `://` or `www.`.
- **Rollback:** revert the PR.

## Notes
- **The corpus found a real gap:** a homoglyph scheme (`һttps://evil.example`) slipped past `sanitise_text`. That function's URL pattern needs a word boundary before the scheme, and the Cyrillic `һ` is a word character. `_LINKISH` now refuses it. `sanitise_text` itself (protected, ADR-065) has the same blind spot for stored model text. I propose a follow-up: there, treat any `://` after a word character as a link.

## Progress log
- The suite (48 tests, including the 8 seeded regressions), test_blocks and test_output_checks pass: 75 in total.

## Definition of done
- [x] Targeted tests pass.
- [x] check-fast passes.
