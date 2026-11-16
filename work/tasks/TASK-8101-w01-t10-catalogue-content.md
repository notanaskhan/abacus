---
id: TASK-8101
title: W-01-T10 Catalogue content v1 as a reviewed import document (55 Connect rows plus 7 portal-only client feeds)
spec: SPEC-659
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: green
status: in-review
branch: w01-t10-catalogue-content
created: 2026-11-15
updated: 2026-11-15
---

## Objective
The catalogue's first reviewed content, imported as data (DEC-5075).

## Built
- `backend/src/abacus_tools/catalogue/connect_v2.yaml` (62 rows); the v2 document gains `writes` (checked against the write-capability registry, never stored).
- `tests/unit/integrations/test_w01t10_catalogue_content.py` (counts, category totals, canvas order, DF-34, OQ-4, L10, DEC-89).
- The W-01 AC suite imports it as the operator would and turns the fakes on: AC-2, AC-24, AC-31 strict xfails removed (they pass); AC-7 both admins reach connect.

## Partly built
- The staging import (62 rows) and the DF-36 sign-off are Ayush's (human to-do).

## Progress log
- 2026-11-15: built; unit and AC suite green; stacked on #2100.
