# Form 1065 line sets review (CPA memo): TY2025 and TY2027

| Field | Value |
|---|---|
| What is reviewed | The `tax_form_lines` drafts for Form 1065 (T-05-T21, TASK-7409): Schedule L (lines 1 to 22), Schedule K (1 to 21), Form 8825 expense and rent lines, Schedule M-1, Schedule M-2 (1 to 9) and the two M-3 difference keys, 112 rows each; totals are marked `mappable: false` |
| Why | DEC-76 and DEC-4408: reference sets are published by two people only after a CPA confirms them. The entity workbook maps to these keys (C9, T-05-T26) and `tax.account_mapper` may answer only with them (T-05-T23) |
| Drafts | outside git (`refdata-drafts/ty2025/`, `refdata-drafts/ty2027/`); their canonical SHA-256 is pinned in `backend/tests/golden/reference_sets/tax_form_lines.json` |
| Prepared by | builder (T-05-T21), Thu Nov 12, 2026 |
| Reviewers | the tax CPA (named in the vault, V-reference; never in git) |
| Status | **review requested; nothing below is signed**. TY2027: the IRS has not released the TY2027 Form 1065; the draft carries TY2025's lines forward and is not published before the forms are |

## 1. Schedule L (TY2025)
- CPA: ☐ lines 1 to 22 and their labels against the 2025 Form 1065 Schedule L; ☐ the contra lines
  (2b, 9b, 10b, 12b) are `contra_asset`; ☐ 14 and 22 are totals.

## 2. Schedule K (TY2025)
- CPA: ☐ lines 1 to 21 (3a to 3c, 4a to 4c, 6a to 6c, 9a to 9c, 13a to 13e, 14a to 14c, 15a to
  15f, 17a to 17f, 18a to 18c, 19a, 19b, 20a to 20c) against the 2025 Schedule K; ☐ line 16
  (Schedule K-2) is left out as a pointer, not a line to map.

## 3. Form 8825
- CPA: ☐ the line numbers of rents and of each expense line against the current Form 8825
  revision (the keys are names, so a renumbering changes the `line` field only).

## 4. Schedules M-1, M-2 and M-3
- CPA: ☐ the M-1 lines used for the book-to-tax bridge; ☐ M-2 lines 1 to 9; ☐ that "M-3 perm."
  and "M-3 temp." suffice for the T-05 bridge until T-06's E4.

## Drafts and sign-off

| Draft file | SHA-256 | Reviewer | Date | Vault reference |
|---|---|---|---|---|
| `tax_form_lines-1065-ty2025.draft.json` | `52cbfdd1fa6093302c491bc2b0ee1ec5dd87aa0ba3a5cfad20d44c806bf753dc` | | | |
| `tax_form_lines-1065-ty2027.draft.json` | `3dad221081180313fbe285e079e5a5af5ad756d3a57318be9798201b2a0030a9` | | | |
