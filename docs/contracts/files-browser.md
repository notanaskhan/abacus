# Files browser (v1, stub)

| Field | Value |
|---|---|
| Register row | proposed for the register (N-01 §8.1; chapter 01 owns the numbering) |
| Version | v1 |
| Status | stub (N-01-T02, 2026-10-27); 404 with `files.browser` off, 501 `not_implemented` with it on until N-01-T19 |
| Provider epic | N-01 |
| Consumers | FIL-01; folder providers and badges from A-07, R-02 and N-02 (signed copies) |
| Freeze sprint | S16 Contract Monday (Mon May 31, 2027) |
| Flag | `files.browser` (default off, expires 2027-01-25, DEC-137) |
| Spec | SPEC-380 Stories 7, 8; `docs/plan/epics/N-01.md` §3.7, §3.8 |
| ADRs | ADR-158 (client-scoped files), ADR-004, ADR-024, DEC-33, DEC-43 |

## 1. Purpose
A read-only view of a client's documents: client › permanent file or year › work item › folder (Source documents, Workpapers, Correspondence, Deliverables, Signed authorizations), with a drawer per document. No write in v1 (DV-10).

## 2. Who may call it
| Operation | Method and path | Matrix action | Agent or system principal |
|---|---|---|---|
| Tree | `GET /v1/files/tree?client_id&expand` | `evidence.read_metadata` | denied |
| Folder | `GET /v1/files/folders/{folder_ref}/items?q&cursor&limit` | `evidence.read_metadata` | denied |
| Drawer | `GET /v1/evidence-items/{item_id}/drawer` | `evidence.read_metadata` (+ `evidence.read` for content fields) | denied |
| Access log | `GET /v1/evidence-items/{item_id}/access-log?cursor&limit` | `evidence.read_access_log` | denied |

A client principal answers 404 (portal Files is not in MVP-1), then the action (403), then the flag (404), then 501. Walls answer 404; no count includes a hidden item.

## 3. Shapes
`backend/src/abacus/modules/evidence/files_contract.py`: `FileTreeOut`/`TreeNode`, `FolderItemsOut` (list envelope plus `documents`, `virtual`), `FileRow`, `VirtualChild`, `DrawerOut` (`TieOut`, `LinkOut`, `VersionOut`, `RetentionOut`, `SignOffSlotOut`), `AccessLogRow`. Status words: `file_document` in `docs/product/status-vocabulary.yaml`. Totals and ties are computed by code (ADR-050).
