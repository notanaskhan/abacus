# TPL-19 · Portal mobile specimen · Feld, 390 px

| Field | Value |
|---|---|
| Route and params | Gallery only: `/components/specimens/tpl-19?st=<letter>&as=claire-feld&clock=2026-09-14T09:24:00-05:00` (`as=mira-kapoor` for i). Production twin POR-19 (R-03, 2029) and every POR screen at 390 |
| Template and host frame | T7-M (390 × 844, `rounded-phone`) · `Wave 0 - Templates.dc.html#tpl19`; F-05 `PortalLayout variant="mobile"`, `MobileTabBar`, More sheet |
| Surface | portal (white-labelled) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-19 Portal mobile specimen - Feld- camera capture/` (README.md, spec.md; **no screenshots**, no revision.md) · HANDOFF_VERSION 2026-10-21 sha256:9308819d |
| Epic and tasks | F-06 · F-06-T01; F-06-T02 seed (Feld binder); F-06-T06 frame 9; F-06-T10 frames 1, 2, 7; F-06-T11 frames 5, 6 and lock; F-06-T12 AC suite |
| Manifest status | planned |

Code: specimen `apps/web/src/gallery/specimens/TPL-19/` over the Feld 2025 binder (`apps/web/src/fixtures/seed/binder-detail.ts`, extended by F-06-T02). Copy keys: `TPL-19/copy.ts`.

## Frame-to-letter map (DF-03, DEC-800)

DF-03 asked for lettered states with screenshots; none were delivered (the README has no screenshot table). T01 letters the frames in the canvas order:

| Letter | Frame | Scope |
|---|---|---|
| a | 1 Home | in |
| b | 2 Documents | in |
| c | 3 Camera, page 1 | **deferred (DEC-97 → R-03)** |
| d | 4 Camera, page 2 ("Done — 2 pages") | **deferred (DEC-97 → R-03)** |
| e | 5 Review & assign | in (cut-list order 1) |
| f | 6 Uploaded | in (cut-list order 1) |
| g | 7 More sheet | in |
| h | 8 Low-quality warning | **deferred (DEC-97 → R-03)** |
| i | 9 Mobile sign (Mira) | in |
| j | camera permission off (caption only) | **deferred (DEC-97 → R-03)** |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a · Home | `claire-feld` | E0 Mon Sep 14, 2026, 9:24 AM CT | E0 | portal home: 2025 Tax Return card (amber ring, "2 documents still needed"), two to-dos, the team card | F-06-T10 |
| b · Documents | `claire-feld` | E0 | E0 | 2025 Binder: 2 to do (Form 1095-C, Estimated tax payments), 4 received, 1 provided | F-06-T10 |
| c, d, h, j | `claire-feld` | E0 | — | none: each renders a "Deferred (DEC-97)" placeholder; no production component | deferred |
| e · Review & assign | `claire-feld` | E0 | E0 | two captured pages; the stitched file name, page count and size come from props (stitching is R-03's, server side) | F-06-T11 |
| f · Uploaded | `claire-feld` | E0 | E0 | the 1095-C request `uploaded` Sep 14; title pill "1 to do" | F-06-T11 |
| g · More sheet | `claire-feld` | E0 | E0 | household client: no Approvals scope in C5 `/v1/me` | F-06-T10 |
| i · Mobile sign | `mira-kapoor` | E0 | E0 | E6 at 390: "1 of 2 signed", step chips, spouse fields, sticky bar 72 | F-06-T06 |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/portal/home`, `GET /v1/portal/binders/…` (R-01, live) | as POR-02, POR-03 | portal scopes (C5) | Approvals appears only when the C5 scope grants it |
| read | C7 envelope view (N-02) for i | `EnvelopeVM` | `envelope.read` | as TPL-16 |
| write | none from the kit | Upload, Ignore and Sign are callbacks | — | — |

## Status
Request rows use F-05-T36's portal request words; "2 to do" / "1 to do" amber pill; `envelope.partially_signed` on i.

## Copy
`TPL-19/copy.ts`, verbatim: "Good morning, Claire" · "2025 Tax Return" · "We're reviewing your return" · "2 documents still needed · extended due date Oct 15, 2026" · "Upload 2 documents" · "1 new message from Kevin Osei" · "Could you send the 1095-C when you have a moment?" · "Your Brightwater Hale team" · "2025 Binder" · "Tap to upload or take a photo" · "Photos of multi-page documents are combined into one PDF" · "Upload…" · "Ignore" · "4 received · 1 provided by Brightwater Hale" · action sheet "Take a photo", "Choose a file" · review sheet ("Retake page 2", "Add a page", "Add to request", "Something else", "Upload") · "✓ You uploaded Sep 14" · "Matched to this request" · More rows (Questions, Deliverables, People & access, Security, Sign out) · "Form 8879 · TY2025" · "Adopt signature & sign…" · "Deferred (DEC-97)" · frames 3–6 caption "Alternate: client uploads by camera instead of email (not the seeded demo day)".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Documents | POR-03 | live |
| Request card | POR-04 | live |
| Sign tab, i | POR-06 / TPL-16 (N-02) | planned |
| Messages | POR-07 | planned |

## Acceptance
- TPL-19 acceptance: T7-M shell (56 header with the firm brand, white cards on the shell ground, bottom tab bar Home · Documents · Sign · Messages · More).
- TPL-19 acceptance: open requests match TPL-07 and the firm side (2 to do → 1 after upload; Feld Intake 2 → 1).
- TPL-19 acceptance: frames 3–6 carry the alternate-path caption; the seeded Sep 14 story stays the 9:12 AM email filed by INB-02.
- TPL-19 acceptance: upload progress uses the amber ring; the receipt reads green-ink "✓ You uploaded Sep 14".
- TPL-19 acceptance: the mobile signing frame hands off to TPL-16 and reads "1 of 2 signed".
- TPL-19 acceptance: no Accrued branding; no blue.

## Figures
2 to do → 1 to do; Feld Intake 2 → 1; 4 received, 1 provided. Proven by `tax.foot.test.ts` (F-06-T02).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, hamburger side drawers, the desktop centred nav on mobile, tiny tap targets, any Accrued branding, red for missing documents.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| c, d, h, j | Not built; "Deferred (DEC-97)" placeholders | v1 capture is the native file input with server stitching | DEC-45, DEC-97, R-03 S59–S63 |
| e | The action sheet's "Take a photo" is `<input type="file" accept="image/*" capture="environment">` | DEC-45 | DEC-45 |
| i | sticky bar 72 (TPL-19's own); production POR-06 uses 64 | F-06 §11.2 Q4 | DECISIONS.md |
| i | "Adopt signature & sign…" carries an ellipsis | Q7 | DECISIONS.md |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a, b, e, f, g, i | C against canvas recaptures (0.20 / 3 %, advisory); D geometry (390, 44 × 44, 48 primaries, bar 72) | not run | DF-03 delivered no screenshots; upload ring masked; locked in F-06-T11 |
| c, d, h, j | — | — | deferred |

## Open gaps
- DF-03 delivered no lettered screenshots; the map above is DEC-800 and changes only with a new handoff.
