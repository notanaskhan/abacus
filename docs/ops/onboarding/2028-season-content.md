# 2028 season onboarding: firm content and load dates (F-09-T192)

Agreed with Q-04's onboarding kit (`docs/runbooks/pilot-onboarding.md`) on 2026-11-12 (the solo
builder holds both lanes, AMENDMENT-solo). Q-04-T093 schedules the loads from this list.

**Rule (AGENTS 16; CLAUDE.md working agreement 2):** firm content is database content. Every item
below loads through the firm's own screens or an import endpoint, by a person at the firm (or, for
the synthetic firm, by `make seed-staging` through the same service APIs). None of it is a commit,
a constant, a migration or a seed file in the repo, so a load costs no deploy.

**Window rule:** loads land in Nov–Dec 2027, in a Tuesday slot outside a deadline week
(`make windows`); nothing loads between Jan 15 and Apr 15, 2028 (the busy-season freeze, ADR P-29).

## Firms

| Firm | Status | Agreement | Load date (CT) |
|---|---|---|---|
| PF-X1 (synthetic, DEC-1530, DEC-4100) | test pilot firm | none needed | **Tue Nov 16, 2027**, 19:00 slot; reload on any staging rebuild (`make seed-staging`) |
| Real firms | none signed: season-2 agreements (F-09-T163) and 2028 pipeline contracts (F-09-T189) are open; no live firm (DEC-1391) | — | each firm gets a row here when its agreement is filed, with a load date before Jan 15, 2028 or after Apr 15, 2028 |

## Content list per firm

The same list for every firm; a firm's row names which items it supplies and which it takes from
the platform defaults. The owner at the firm is the role the kit names.

| # | Content | Owner at the firm | Loads through | Kit step | PF-X1 |
|---|---|---|---|---|---|
| 1 | Clients and contacts | firm admin | CLI-06 bulk import, `POST /v1/client-imports` | §4 | the scenario's client list (through the import service) |
| 2 | PBC template workbook (engagement templates) | quality partner, approved by another | KNW-01 import, `POST /v1/methodology/templates/{name}/versions` | §5 | Brightwater Hale's methodology and binders slices |
| 3 | Email templates: Reminder, Invitation, Signature request, Deliverable ready, Confirmation request, Reconnect request (and any key the firm's modules register) | firm admin | POR-20 or `POST /v1/firm/email-templates/import` (counsel-approved bundle, dry run first, fresh MFA) | §6 | Brightwater Hale's six templates, through the import route |
| 4 | Organizers and questionnaires (tax firms) | tax partner | the organizer and questionnaire editors (T-02) or their import | — | Brightwater Hale's tax content slice |
| 5 | Firm standards and methodology (audit firms) | quality partner | the methodology importer (RB-49) | §5 | Brightwater Hale's standards slice |
| 6 | Report and letter templates | quality partner | the report templates import (A-07) | — | Brightwater Hale's report templates slice |
| 7 | Branding, portal settings, follow-up policy, sender domain | firm admin | ADM-10, sending domains (`docs/runbooks/r01-portal-flip.md` rows 0–2) | §6 | brand slots on the synthetic host; sender domain on the fake SES |

Platform keys that must be imported per environment before any switch that sends
(`notification.mention`, `portal.sign_in_code`, the follow-up keys) are the platform's, not a
firm's: kit step 0.4.

## Open
- A real firm's row, its supplied items and its date, once F-09-T163 or F-09-T189 files an
  agreement.
- Counsel's approval of each firm's email template bundle (F-09-T115's pattern) before it is
  imported.
