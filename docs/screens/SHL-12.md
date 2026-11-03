# SHL-12 · Sign-off modal

| Field | Value |
|---|---|
| Route and params | Overlay `?ov=signoff:<targetType>:<targetId>[:<level>]` (O3 sheet) over any firm route; bulk (f) from SHL-04 and the review queue. Artboards: `/components/screens/SHL-12?st=a,ap,b..h&frame=1` |
| Template and host frame | O3 sheet modal 500, top 52 · `Wave 0 - Shell.dc.html#shl12` |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-12 Sign-off modal/` (README.md, spec.md; no revision.md) |
| Epic and tasks | P-04 · sign-offs P-04-T18 · modal P-04-T48 · bulk P-04-T49 · independent AC tests P-04-T20 · parity P-04-T58 · this contract P-04-T60 |
| Manifest status | fixture (`routes/manifest/shl.ts`) until the staging walk; live where its host screen is |

Code: `src/screens/SHL-12/{index.tsx, Bulk.tsx, copy.ts, scenarios.ts, SHL-12.test.tsx, SHL-12.bulk.test.tsx, SHL-12.ac.test.tsx}`, `src/fixtures/scenarios/SHL-12.ts`.

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 9:41 AM CT | Eligible: the ladder, the target's content hash, "Sign off as {role}" | live |
| ap (a′) | hannah-leclerc | 9:41 AM | Signed: the ladder's disc filled, the signature line | live |
| b | hannah-leclerc | 9:41 AM | Blocked by open review notes (`notes_open`) | live |
| c | marcus-delaney | 9:41 AM | Blocked: the viewer prepared it (`same_preparer`, R-SO-3) | live |
| d | hannah-leclerc | 9:41 AM | Blocked: independence not confirmed | live |
| e | hannah-leclerc | Thu Sep 24, 2:15 PM | Stale after a change since sign-off (`sign_off.went_stale`) | live |
| f | hannah-leclerc | Thu Sep 24 | Bulk sign-off of eligible items | live |
| g | thomas-whitcombe | 9:41 AM | EQR viewer: read-only, the EQR ladder row | live |
| h | daniel-reyes | 9:41 AM | Tax final approval (L4; only `tax/approval.py` records it) | live |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons |
|---|---|---|---|---|
| read | `GET /v1/sign-offs/eligibility?target_type=&target_id=` | the ladder, the blockers in words | `sign_off.read` | blockers name their reason codes |
| read | `GET /v1/sign-offs?target_type=&target_id=` | the target's sign-offs | `sign_off.read` | — |
| write | `POST /v1/sign-offs` (fresh MFA for L3 and up) | the sign-off at the content hash | `sign_off.create` (the level's rule is the service's) | 409 `notes_open`, `same_preparer`, `content_changed` |
| write | `POST /v1/sign-offs:bulk` | per-item outcomes | `sign_off.bulk` | each item checked alone |

## Copy
Verbatim from spec.md through `src/screens/SHL-12/copy.ts` (the copy registry): "Sign off as {role}", "Prepared · {initials}", "Reviewed · {initials}", the blocker sentences, "Changed after sign-off".

## Links
| From | To | Planned or live |
|---|---|---|
| Blocker "Open notes" | SHL-14 notes on the target | live |
| Inbound | every reviewable host (AUD-*, TAX-*, NOT-03, SHL-04) | per the manifest |

## Deviations
1. a′ is a sub-state artboard beside the lettered states; its parity key is `ap`.
2. Field ticks are sign-offs: an L1 tick on a field (SHL-09, EBP-02's provisions) records through the same service at the field's target, so the ladder and the stale rule are one.
3. Import-author variant: an import's approval (SHL-16) is the checkpoint's author's ladder, never the modal's preparer rule; the modal reads the checkpoint's own facts.
4. Fixture dates follow DF-13 (each artboard at its README clock; e and f on Sep 24).

## Build notes (the build-screen skill)
The modal never decides eligibility: it renders `GET /v1/sign-offs/eligibility` and posts with the content hash it was shown.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, e | C (locked) | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | P-04 lock; axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| ap, c, d, f, g, h | C | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | report-only (ap is a′); axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| host | D | not run | O3 sheet 500, top 52 (`e2e/visual/tier-d-review.spec.ts`) |

Gate: chapter 04 §9.3 keeps Tier C report-only, so the locks are listed and reported, not blocking (DEC-1970). Keyboard: Escape closes the topmost layer and focus returns to the opener.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| View changes; the checks' Open notes (Opens AUD-17 · review notes and sign-off matrix) | AUD-17, planned in the manifest; a `PlannedLink` until it has a builder | planned (P-04-T60) |
| The checks' Confirm independence (Opens ENG-05 · team roles (later)) | ENG-05, planned in the manifest; a `PlannedLink` | planned |
| The checks' Open issues (Opens TAX-06 · return issues) | TAX-06, planned in the manifest; a `PlannedLink` | planned (P-04-T60) |
