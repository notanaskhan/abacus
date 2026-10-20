# C2 · Status registry (v1)

| Field | Value |
|---|---|
| Register row | C2 in `docs/contracts/README.md` |
| Version | v1 |
| Status | frozen (2026-10-21; snapshot `backend/tests/contracts/c2_status_registry/v1.json`) |
| Provider epic | F-03 (YAML F-03-T04, codegen F-03-T09) |
| Consumers | all modules and screens |
| Freeze sprint | S1 (starts 2026-11-02); frozen early |
| Flag | none |
| Spec | `docs/specs/SPEC-306-s1-data-model.md` |
| ADRs | ADR-138; DEC-08 |

## 1. Purpose
Every status word is authored once, in `docs/product/status-vocabulary.yaml`, and three things are generated from it:
- the backend StrEnums and CHECK lists (`abacus.kernel._statuses`);
- the OpenAPI enums;
- the UI data (`packages/ui/src/status.gen.ts`, read through `registryWord`).

Consumers rely on two rules: an API status is always one of its object's stored codes, and a derived code (`overdue`) is never stored.

## 2. Who may call it
It's a build-time contract, so it has no routes. `make regenerate` writes the outputs, and `make check-fast` fails when they're stale.

## 3. Models
- `EngagementStatus`: the 8 lifecycle codes.
- `RequestStatus`: draft · requested · uploaded · received · returned · not_applicable.

Further objects join as their API fields adopt the generated enums; joining is additive.

## 4. Status words
Labels, client labels, variants and context labels come from the YAML. The `match` variant is never used for a status.

## 5. Human-only actions
None.

## 6. Errors
None at runtime. A stale generated file fails `check-generated`.

## 7. Audit and outbox events
None.
