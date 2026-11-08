# workpapers

Zone: amber. Pre-registered by F-03-T08 (ADR-140); empty until its first epic.

Will own (docs/plan/03-backend-architecture.md §2.2): Workpapers, sections, versions and cells; sheets, columns, rows, cells and views; agent columns; procedures; leadsheets; tie-out checks; test attribute results; the formula DAG.

## Adding to the planning workpapers (A-04-T39)
A reviewable registers with `review.api.register_reviewable`, a suggestion target with its applier in
`agents`, an exception route with `assurance`'s route registry, and a section kind in the methodology
pack (never here). Operating notes: `docs/operations/audit-planning/README.md`.

## EBP modes (A-05; A-05-T62)
The section drafter's EBP modes (`ebp_trust`, `ebp_form5500`, `related_parties`, ...) live in `assurance/*_mode.py` and register their mappings with `agents.section_sources`. They read masked pages and code's numbers as facts and propose only (C3 suggestions; no tools). They stay synthetic-only until A-05-T63's clearance. Runbook: `docs/runbooks/ebp-modules.md`.
