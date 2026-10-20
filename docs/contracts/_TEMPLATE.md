# C<n> · <Contract name> (v1)

| Field | Value |
|---|---|
| Register row | C<n> in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub / frozen / live |
| Provider epic | <epic ID> |
| Consumers | <epics, modules, screen IDs> |
| Freeze sprint | S<n> (starts <date>) |
| Flag | `<module>.<flag>` (default off, expires <date>) |
| Spec | `docs/specs/SPEC-<nnn>-*.md` |
| ADRs | <ADR-nnn, P-nn> |

## 1. Purpose
One paragraph: what the contract lets consumers rely on.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| | | `<module>.<verb>` | | allowed / denied |

## 3. Models
Each Pydantic model, its fields, and the data classification tag of every field (ADR-031). Link to the code path.

## 4. Status words
The codes and labels used, from `docs/product/status-vocabulary.yaml`. Never invent a synonym (`docs/product/glossary.md`).

## 5. Human-only actions
Actions that an agent or system principal is denied at the matrix, `require_live_human` and the database check (INV-1). State which.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 409 | `{"detail": "...", "facts": {...}}` | |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| | | |

## 8. Example payloads
Brightwater Hale seed examples only (synthetic tenant). One per case the consumers' screens need, including the error cases.

## 9. Consumer contract tests
Path under `backend/tests/contracts/<name>/` and the TypeScript fixture assertions. These run in the provider's CI.

## 10. Versioning
Additive changes in place. Breaking changes ship as v2 with one sprint of overlap (see `docs/contracts/README.md`).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | |

## 11. Open points
Decided points are recorded in `docs/product/decision-log.md`; cite the DEC number here.
