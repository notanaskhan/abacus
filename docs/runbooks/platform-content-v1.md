# Platform content v1: help articles, status catalogue, regions, support hours (G-04-T20)

Production platform content is database rows, loaded from a reviewed content folder that never
enters this repository (AGENTS.md rule 16; DEC-5702). Two founders take part: one loads and drafts,
the other publishes (help articles refuse `approver_is_drafter`).

## The content folder (kept outside the repository)

```
status_components.json   [{key, label, kind: core|integration, integration_key?, display_order?, active?}]
regions.json             [{code: us|eu|uk, label, status: live|planned, planned_label?, storage_label?, backup_label?, inference_label?}]
support_hours.json       {"value": {...the support_hours setting...}, "expected_version": 0 for the first load}
articles/<slug>.json     one help article each (schema v1 blocks: heading, paragraph, list, note, screen_link)
```

## Steps (staging first, then production)

1. Check the folder: `python -m abacus_tools.platform_console content-import --dir <folder> --operator <you> --reason "<why>" --dry-run`.
2. Load it as `abacus_ops` (the same command without `--dry-run`); every write is one transaction and audited to `platform_audit_events`.
3. The other founder lists the drafted articles in the console's Publications section and publishes each (`article-publish --id … --operator <them>`).
4. Email templates for the new notification kinds: `POST /v1/platform/email-templates/import` (R-01's import), one row per kind.
5. Check SHL-05's Help articles and System status tabs on the target environment.

Rollback: a status component is retired with `"active": false`; a region row is edited back; a
setting is put again at its current version; a published article is withdrawn (`article-withdraw`).
