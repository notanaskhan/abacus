---
name: temporal-workflow
description: How to write Temporal workflows and activities safely — determinism, versioning, signals, child workflows, tests. Use for any workflow or engagement agent code.
---

# Temporal workflow pattern

**Reference:** `docs/architecture/reference/temporal-workflow.md` (from the walking skeleton).

## Determinism (ADR-017)
Workflows only orchestrate. **All I/O happens in activities**: database, HTTP, files, model calls, clocks, randomness. Use `workflow.now()` and `workflow.random()` inside workflows, never `datetime.now()` or `random`.

## Versioning (ADR-090)
Any change to workflow logic that could alter running histories goes behind `workflow.patched("<change-id>")`. Never edit a running path in place.

## Long-running agents (ADR-062)
Events arrive as signals. Timers schedule work. Periodically continue-as-new with carried-forward state. Specialists are child workflows. State is rebuildable from Postgres (ADR-095).

## Payloads
Encrypted by the payload codec (ADR-017). Pass IDs, not large data.

## Tests
- Replay test with recorded histories (required check)
- Time-skipping environment for multi-day or multi-week behaviour (ADR-077)
