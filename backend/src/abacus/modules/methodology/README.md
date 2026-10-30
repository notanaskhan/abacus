# methodology

Zone: amber. Pre-registered by F-03-T08 (ADR-140); empty until its first epic.

Will own (docs/plan/03-backend-architecture.md §2.2): Engagement templates and versions, program steps, sheet and form definitions, standards sets, firm standards, threshold policies, frameworks, note and report templates, knowledge items, methodology imports. Takes over `methodology_*` from engagements.

## Report templates (P-11-T06; migration 0460; DEC-1350)
- `report_templates.py`: firm wording for C11's generated documents. `report_templates` (one per
  family and name), insert-only `report_template_versions` (DocBlock body, clause library,
  declared variables, synthetic sample data, `content_sha256`) and insert-only
  `report_template_publications` (`published` or `deprecated`, a person and their second factor).
- Import stores the next version (reporting validates the bundle first); publish is a person's,
  never the importer's (`publisher_is_importer`), 409 `already_published` for the current one;
  republishing an earlier version rolls back. The current version is computed, never stored.
- Rows arrive only through the import route or the scenario loader's service call; never a
  migration, constant or seed.
