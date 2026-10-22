---
id: TASK-371
title: Client record, entity attributes, contacts and engagement contact designations (F-03-T25)
spec: SPEC-025
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T25
branch: f03-t25-client-record
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Copperleaf reads non-attest with Tess Moreno (owner) and Ben Ashby (approver of record) as
contacts, and no plaintext TIN column exists." (chapter 03 §3.5 story 5.1; CLI-04g)

## Plan (red)
- Migration 0082: client record columns (kind, status, primary office, relationship partner,
  risk tier, `is_attest_client`, portal status, practice-management ref); entity attributes (no
  TIN); `contacts` (organisations; email unique per client, case-insensitive);
  `engagement_contacts` (engagements; insert-only designations). `is_attest_client` is derived by
  a reviewed SECURITY DEFINER trigger on `engagements` (DEC-128); the app has no UPDATE on it.
- organisations: models, repository, `set_client_record`, `set_entity_attributes`, `add_contact`,
  `client_record`, `contact_client`, `attest_client_of` (in the caller's unit of work, as
  `create_client`).
- engagements: `contacts.py` (`designate_contact` behind new action
  `engagement_contact.designate`, partner and manager; `engagement_contacts` behind
  `client_contact.read`); registers the `attest_client` condition lookup (F-03-T24).
- No routes yet: CLI-02/04 (P-07) build them, contract first.
- Rollback: revert, downgrade 0082.

## Definition of done
- [x] `tests/integration/test_client_record.py`: story 5.1 (Copperleaf non-attest, Tess Moreno
  and Ben Ashby, Ben approver of record), no taxpayer-ID column, attest derivation through the
  lifecycle as the app role, the app can't set the flag, one contact per email, a designation
  only for the engagement's client's contacts
- [x] `tests/unit/engagements/test_attest_client_trigger.py`: trigger lists match `gate_policy`
- [x] Backend unit, integration schema suites; `make check-fast`

## Progress log
- 2026-10-22: built in one session. The chapter's "organisations refreshes it on the event" is
  replaced by a trigger (DEC-128): module direction forbids organisations reading engagements, and
  the INV-5 test pins one write per transition.
