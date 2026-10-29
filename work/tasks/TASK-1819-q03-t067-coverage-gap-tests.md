---
id: TASK-1819
title: Coverage gap tests for red modules, part 1 (Q-03-T067)
spec: SPEC-000  # chapter 10 row 2 and the Q-03-T067 row; each file cites the contract it is written from
acceptance_criteria: [AC-1]  # Q-03-T067: red modules toward 97% line by Fri Apr 30, 2027
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T067
branch: s13r-q03-t067
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Tests for the red modules' uncovered behaviour, written from their contracts (module docstrings, G-02 §4.5 AC-13, ADR-139, SPEC-349), never from the uncovered lines alone, so the floors of DEC-907 can rise toward 97% line.

## Part 1 (this PR)
| Module | Contract | Before (run 40849655921) | After (these files alone) |
|---|---|---|---|
| `kernel/crypto/signing.py` | G-02-T17, §4.5 AC-13: KMS signs the digest, the key that signed is recorded, every failure fails closed | 60.5% | 99% |
| `kernel/crypto/cursor.py` | ADR-139, P-36: sealed under the current key, survives an added key, bound to its associated data | 81.5% | 100% |
| `kernel/uow/placement.py` | SPEC-349 §4, §7; DEC-458, DEC-415 Q9: the engagement decides, a client takes its primary office | 82.5% | 100% |

`tests/unit/kernel/test_q03t067_{export_signing,cursor,audit_placement}.py`, 40 tests.

## Still to reach 97% line (measured gaps, run 40849655921)
identity/authz 87.3% (`__init__.py`: the visibility builders, shared with Q-03-T064's mutation work), ai_gateway 83.9% (`routes/parity.py`, `bedrock.py`, `_anthropic.py`), evidence 93.1% (884 lines over 95 files), audit_trail 94.2% (`exports.py`, `explorer.py`), kernel/uow 93.5% (`relay.py`), kernel/crypto after this PR about 95%. The floors in `backend/coverage-thresholds.yaml` rise from CI's next full measurement, not from these local numbers.

## Progress log
- 2026-10-29: part 1 built; 40 passed.
