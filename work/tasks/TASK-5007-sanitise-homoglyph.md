---
id: TASK-5007
title: "sanitise_text removes links behind a homoglyph scheme"
spec: SPEC-006
acceptance_criteria: [AC-1, AC-2]
risk_zone: red
status: done
branch: task-5007-sanitise-homoglyph
worktree: agentwt
created: 2026-10-26
updated: 2026-10-26
---

## Plan keys
Security fix from TASK-5006's conformance suite (ADR-065; DE-6).

## Plan
- **Root cause:** `ai_gateway/sanitise.py`'s `_URL` needed a word boundary before the scheme. In "һttps://evil.example" the Cyrillic `һ` is a word character, so no boundary falls before "ttps://" and the link survived in stored model text.
- **Fix:** drop the boundary before the scheme. The scheme still starts at an ASCII letter, and `www.` keeps its boundary.
- **Tests:** `tests/unit/ai_gateway/test_sanitise.py` covers SPEC-006 AC-1 and AC-2, which had no direct tests before.
- **Rollback:** revert the PR. Already-stored text isn't rewritten, so earlier rows keep any such link as inert plain text.

## Progress log
- test_sanitise (10), the ai_gateway and agents unit suites (874) and the workflow replay tests (238) pass.

## Definition of done
- [x] Targeted tests pass.
- [x] check-fast passes.
