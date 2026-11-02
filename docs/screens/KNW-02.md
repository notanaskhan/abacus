# KNW-02 · Methodology versions & import review

| Field | Value |
|---|---|
| Route and params | `/knowledge/methodology/$versionId` (Knowledge); `?tab=`, `?ov=approve-version` (the Approve sheet). Artboards: `/components/screens/KNW-02?st=a…f`, `draft` |
| Template and host frame | T3 Prepare frame (the import review) and the version workbook |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/KNW-02 …/` (README.md, spec.md) |
| Epic and tasks | K-01 · import review K-01-T22 (a, a2, b) · versions and approve K-01-T23 (c–f) · independent tests K-01-T24 · journeys and parity locks K-01-T25 (this contract's parity table) |
| Manifest status | planned with path `/knowledge/methodology/$versionId` (fixture-built; live once the methodology slice is on staging) |

## States
| Artboard | Viewer (persona) | Clock | Data condition |
|---|---|---|---|
| a | margaret-okonkwo | Mon Jan 12, 2026, 2:10 PM | v3 imported, Needs review: every parsed step cites a page (step 4 · p. 14) |
| a2 | margaret-okonkwo | 2:10 PM | the Flagged tab: step 7 alone, split pp. 15–16 |
| b | margaret-okonkwo | 1:51 PM | the importer reading 2 files, 41 of 96 pages |
| c | margaret-okonkwo | 2:10 PM | the diff against v2: v3 = 67 steps · v2 = 64 steps |
| d | margaret-okonkwo | 2:10 PM | the standards set: SQMS 1, three EBP types, the default |
| e | margaret-okonkwo | 2:10 PM | the Approve sheet: effective Jan 1, 2026, supersedes v2, the server's checklist |
| f | margaret-okonkwo | 2:31 PM | approved: "Approved · Jan 12, 2026 2:31 PM · Margaret Okonkwo" |

## Journeys
`apps/web/e2e/journeys/knw-02-import-review.spec.ts` (a–f) and J01 step 5w in
`J01-firm-onboarding.spec.ts` (K-01-T25), fixture-first; full stack once the methodology slice is
on (K-01 flag plan).

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a, a2, b, c, d, e, f | C (locked) | — | K-01-T25 (DEC-2075) |
| draft | C report | — | |

## Open gaps
None.
