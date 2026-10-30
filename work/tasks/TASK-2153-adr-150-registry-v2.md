---
id: TASK-2153
title: ADR-150 accepted - write-capability registry version 2 opens W7 (DEC-1280)
spec: SPEC-333
acceptance_criteria: [AC-50]
risk_zone: red
status: in-review
epic: A-02
plan_key: N-02-T18
branch: adr-150-152-accept
created: 2026-10-30
updated: 2026-10-30
---

## Objective

Ayush accepted ADR-150 on 2026-10-30 and asked for W7 (the DocuSeal send) to open. The
registry's own rule: a write opens only through a later schema version, once the decision it
names is accepted. Build that version, open W7 only, and keep every write into a client's system
closed and the generic write gate refusing every call.

## Plan

- `integrations/ports.py`: registry `version: 2`; `enabled` is a bool, allowed only for a shape
  in `OPENABLE_SHAPES` (W7) naming an ADR.
- `abacus_tools/codegen/write_capabilities.py`: version 2 needs ADR-150 accepted; an enabled
  write needs its ADR `status: accepted` (read from `docs/adr/`).
- `write-capabilities.yaml` (protected, changed with the code that needs it): version 2, W7
  `enabled: true`; `_capabilities.py` regenerated.
- `integrations/capabilities.py`: `policy_refusal` refuses an enabled openable shape as
  `own_path` (appended to `REASONS`), so `execute_write` still refuses everything.
- ADR-150 `status: accepted`, README index, DEC-1280; docstrings that said W7 is never enabled.
- Tests: v1-pinned tests move to version 2 with every refusal kept (W1/W2 still cannot be
  enabled, version 3 does not validate, the gate refuses every declared write); new tests for
  the accepted-ADR check and the openable-shape rule; the install test now expects the secret.
- No migration. Rollback: set W7 `enabled: false` and regenerate (the kill switch per firm is
  the flag).

## Progress log

- 2026-10-30: built; unit (integrations, signatures, C20 contract) 207 passed; integration
  (write refusal, A-02-T19 independent, TASK-2152 install) 28 passed.
