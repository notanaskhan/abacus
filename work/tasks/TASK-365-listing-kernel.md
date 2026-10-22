---
id: TASK-365
title: API conventions kernel — list envelope, encrypted keyset cursors, counts minus tile, capped totals, identifier-only error facts, error-code catalogue (F-03-T29)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: amber
status: done
epic: F-03
plan_key: F-03-T29
branch: f03-t29-listing
created: 2026-10-22
updated: 2026-10-22
---

## Objective
ADR-139 (P-36): "Cursors are opaque AES-GCM tokens, counts ignore the tile filter, and a unit test
fails any facts field holding free text."

## Plan (amber)
- `abacus/kernel/listing.py`: `ListPage[T]` (`items, next_cursor, total, total_capped, counts,
  facets`), `clamp_limit` (50 default, 200 max), `query_hash`, `encode_cursor`/`decode_cursor`
  (`CursorInvalid`, 422 `cursor_invalid`), `keyset` (tuple comparison on `(sort, id)`, one row more
  than the page), `page_of`, `status_counts` (over the query without the tile), `capped_total`
  (exact to 10,000), `envelope`.
- `abacus/kernel/crypto/cursor.py`: AES-GCM sealing (ADR-035: cryptography only in
  `kernel.crypto`) under a key derived by HKDF from the payload keyring the deployment already
  holds; the key id rides in the token, so adding a key does not break open cursors. Local runs
  and tests seal with a per-process key. The associated data binds a cursor to tenant, resource
  and query.
- `abacus/kernel/errors.py`: `DomainConflict` and `DomainInvalid` take identifier-only `facts`
  (`check_facts`: snake_case keys; values an identifier or code with no spaces, an int or a bool);
  the API answers `{"detail": code, "facts": {...}}`, `facts` only when present.
- `docs/architecture/error-codes.yaml`: the catalogue of every 409/422 code (162 today), built and
  checked by `abacus_tools.quality.error_codes` in `make check-fast`.
- No migration, no route change, no new dependency. Rollback: revert the commit.

## Not here
Moving existing list routes onto the envelope: each list moves with its own task. Generating the
UI message map from the catalogue: with the first screen that shows these codes.

## Definition of done
- [x] 36 unit tests (`tests/unit/kernel/test_listing.py`), 4 against Postgres
  (`tests/integration/test_listing.py`)
- [x] The backend unit and acceptance suites (14,426 passed)
- [x] `make check-fast`
