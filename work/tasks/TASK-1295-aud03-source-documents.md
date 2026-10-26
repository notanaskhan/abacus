---
id: TASK-1295
title: AUD-03 Source documents · PBC with viewer on the 536 + 490 audit split, states a–g (A-01-T15)
spec: SPEC-330
acceptance_criteria: [AC-1, AC-15, AC-24, AC-26]
risk_zone: green
status: in-review
epic: A-01
plan_key: A-01-T15
branch: s9c-aud03-pbc
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Build AUD-03 (docs/screens/AUD-03.md) in the AUD-02 cockpit: the Source Documents canvas with
"Missing first", folder bands, rows with who owes them and when, "Linked (n)", the 12 px
screening glyph, Overdue and Returned pills and the received row's ··· menu; the 490 viewer
with the Accept / Return strip, the C-34 ScreeningCard, the masked page and "Reveal (logged)",
and the requested row's EmptyState. Every artboard a–g is a fixture scenario with a test.

## Plan
- Route `/audits/$auditId/source-documents` (`?item=`, `?sort=`, `?q=`) behind `audits.cockpit`;
  the manifest gets the path and stays `planned` (its SHL-14 link has no builder, as AUD-02).
- `screens/AUD-03/{index.tsx, copy.ts, scenarios.ts, AUD-03.test.tsx}` on `domain/audits`
  (AuditCockpit; the dock widened to the `--ev-w` token, Viewer tab), `domain/screening`
  (ScreeningCardHost) and `domain/requests` (ReturnDialog, FollowUpSheet).
- `domain/audits/DockViewer.tsx`: a slot above the well, a lit match and the logged reveal
  (`POST …/pii-reveals`, a stale MFA opens `ConfirmItsYou`); the text view (DEC-369) unchanged.
- Fixtures: `fixtures/seed/aud03.ts` (the BrokerWindow and Harborline certification documents,
  the screening cards, the Sep 9, late-September and Sep 21 snapshots) and
  `fixtures/scenarios/AUD-03.ts`; the C5 v1.1 row fields (match, screening, uploaded Sep 11) in
  `seed/audits-index.ts`.
- Gallery artboards a–g; contract deviations and decisions DEC-421.
- No backend change, no migration, no new endpoint.

## Tests
`screens/AUD-03/AUD-03.test.tsx`: one per artboard, loading, error, not found, staff accept off,
offshore (no reveal, text view), each acceptance bullet, the figures and the AVOID list.

## Rollback
Revert the commit; AUD-02 and the legacy board are untouched apart from the shared DockViewer.

## Progress log
- 2026-10-26: built a–g on fixtures (route, screen, DockViewer slot/lit/reveal, seed and scenarios,
  gallery a–g). Targeted pass: AUD-03.test.tsx 28/28; AUD-02, domain/audits, audits.contract,
  screen-parity, scenario-parity, gallery seed-fixtures, masked-text and SHL-08 green.
  link-contract has one failure on main already (AUD-06 contract links, #417, not this task);
  gallery/routes.test.tsx times out only under parallel load (10/10 alone). Playwright parity not
  run (chromium mismatch). DEC-421; contract DV-13 to DV-18 and four open gaps.
