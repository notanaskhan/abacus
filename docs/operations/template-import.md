# Importing a firm's document templates (pilot guide)

P-11-T13 · C11 v1 (`docs/contracts/c11-renderer.md`) · DEC-1350, DEC-1352, DEC-1563

A firm's engagement letters, §7216 consents, representation and governance letters, report
shells, notice responses and cover letters are **database content**. They go in through the
template import, are published by a second person, and are never put in a migration, a constant
or the seed (AGENTS 16). This guide covers one firm's first load and later changes.

## Who does what

| Step | Who | Matrix action |
|---|---|---|
| Import a bundle (dry run, then a draft version) | Firm admin, quality partner or practice leader | `report_template.import` |
| Publish a version | Quality partner or practice leader, with a fresh second factor, never the person who imported it; a partner for a consent template | `report_template.publish`, `consent_template.publish` |
| Roll back | The publisher republishes the earlier version | `report_template.publish` |

The agent and the system never import or publish.

## 1. Write the bundle

A bundle is JSON in the `TemplateImportIn` shape: `family`, `name`, `description`,
`layout_key`, `body` (DocBlocks), `clauses` (the clause library, each with its standard text
and whether it is on by default), `variables` (key, label, value type) and `sample_data`
(synthetic values for the SAMPLE preview).

- **No markup and no URLs.** Text is plain; a variable is `{"type": "var", "key": "…"}`, declared
  in `variables`. Values are resolved by the consumer when a document renders, never typed in
  the template.
- **One purpose per consent.** A `consent_7216` bundle carries its `consent` terms (purpose,
  statement version, counsel attestation, expiry) and places `consent.recipients` exactly once.
  It never names a provider or sub-processor in its text: the recipient line comes from the
  provider-terms register when the consent renders.
- Use the firm's own wording. The Brightwater Hale scenario's bundles
  (`backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/report_templates.py`) show the
  shape with synthetic wording; never copy them into a real firm.

## 2. Dry run

`POST /v1/report-templates/import?dry_run=true` with the bundle. The answer is an
`ImportReport`: `ok`, `errors[{path, code}]` (for example `markup_not_allowed`,
`unknown_variable`, `recipients_block_required`, `recipient_in_text`) and `warnings` (a declared
variable the body never uses). Fix every error and every warning before the real import.

## 3. Import

The same request with `dry_run=false` stores a draft version and audits
`report_template.imported`. Importing an unchanged bundle again stores nothing and says so in
`warnings`.

## 4. Preview and publish

- `POST /v1/report-templates/{id}/versions/{n}/preview` renders the version's sample data with
  the SAMPLE mark. Check the pages before publishing; nothing is stored.
- A second person publishes with
  `POST /v1/report-templates/{id}/versions/{n}/publish` after a fresh second factor. The version
  becomes current and documents rendered from now on use it; `report_template.published` is
  audited.

## 5. Change or roll back

A change is a new import (version n+1) and a new publication. Documents already rendered keep
their version. To roll back, republish the earlier version; to withdraw a template, deprecate its
current version (nothing is current until a version is published again).

## Demo tenant

`make seed-demo SLICE=report_templates` loads Brightwater Hale's twelve templates this
way: Grace Holloway imports each one and Margaret Okonkwo publishes it, into the synthetic tenant
only.
