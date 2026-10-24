# SHL-06 · Firm sign-in

| Field | Value |
|---|---|
| Route and params | `/signin/callback?to=<safe path>` or `?error=<code>`: the BFF's landing (P-01 §5.1), outside the firm workspace. a–f are the hosted provider's pages, reached by a top-level navigation to `GET /v1/auth/sign-in?return_to=`. Artboards: `/components/screens/SHL-06?st=g\|error\|expired` |
| Template and host frame | T15 AuthCard (the 400 card) in the firm's own window: no toolbar, the shell colour, the block 133 from the top · `Wave 0 - Shell.dc.html#shl06` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-06 Firm sign-in/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-01 · BFF P-01-T09 (TASK-906, ADR-165); g, the error state and the auth client P-01-T11; Tier C lock and journeys P-01-T16 |
| Manifest status | live (`routes/manifest/shl.ts`; no path in the area tree, the landing is reached only by redirect) |

## States
7 artboards in the handoff; g is built here, a–f are hosted (P-01 §2.2).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a–f | hannah-leclerc | Mon Sep 14, 2026, 9:24 AM CT | E0 | The provider's hosted pages (WorkOS AuthKit; locally the fake sign-in server) | hosted, not built (Deviations) |
| g | hannah-leclerc | same | E0 | The BFF landed the browser with `?to=`; `POST /v1/auth/refresh` and `GET /v1/me` are in flight | built · live |
| error (undesigned) | hannah-leclerc | same | E0 | `?error=<code>` from the BFF: `mfa_required_at_sign_in`, `unknown_staff_user` or `sign_in_failed` | built · live |
| expired (undesigned) | hannah-leclerc | same | E0 | The landing's refresh answers 401 `session_expired` or `session_refresh_reused` | built · live |

Loading is g itself. Not-allowed is the error state. A 403 from `/v1/me` (no firm yet) is not an error here: the page opens the return path and the shell shows its no-firm state.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| navigate | `GET /v1/auth/sign-in?return_to=&reauthenticate=` | 302 to the provider | `PRE_SESSION` (ADR-165) | anyone; `reauthenticate=true` for step-up (ConfirmItsYou) |
| write | `POST /v1/auth/refresh` + `X-Abacus-CSRF: 1` | `SessionTokenOut {access_token, expires_in}`; 401 `session_expired` · `session_refresh_reused` | `PRE_SESSION` (cookie) | the session's person |
| read | `GET /v1/me` | `MeOut`, cached for the shell | `OWN` | the session's person |
| write | `POST /v1/auth/sign-out` (bearer) | `SignedOutOut` | `OWN` | the session's person (SHL-03, ClientHome) |

The access token is kept in `app-core/auth` memory only. A fresh page load refreshes it from the cookie; a token within 30 s of expiry is refreshed before the next request; a 401 refreshes once and replays a request without a body, or sends the person to sign-in with the current route (path and query) as `return_to`. A 401 within 10 s of the landing's refresh is not retried (the loop guard).

## Status
None.

## Copy
Copy keys live in `screens/SHL-06/copy.ts`.

| Key | String | Source |
|---|---|---|
| `title` | "Sign in to Accrued" | spec.md frame 1 |
| `signingIn` | "Signing in…" | spec.md frame 7 |
| `links` | "Privacy" · "Terms" · "System status" | spec.md geometry |
| `error.title` | "Sign-in didn't complete" | the app's existing callback copy (undesigned state) |
| `error.retry` | "Sign in again" | same |
| `error.reasons.mfa_required_at_sign_in` | "Your sign-in needs a second factor. Turn on two-step verification with your sign-in provider, then sign in again." | DEC-149 |
| `error.reasons.unknown_staff_user` | "This sign-in isn't linked to anyone at your firm. Ask your firm's administrator for an invitation." | DEC-149 |
| `error.reasons.session_expired` | "Your session ended. Sign in again to carry on." | DEC-149 |
| `error.reasons.session_refresh_reused` | "For your security, this session was ended. Sign in again." | DEC-149 |
| `error.reasons.session_rejected` | "Your sign-in wasn't accepted. Try again, or ask your firm's IT team." | DEC-149 |
| `error.reasons.sign_in_failed` | "The response from the sign-in page couldn't be used." | the app's existing callback copy |

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| g, after `/v1/me` | the safe return path (`to`), else `/` | live (not a screen link: the path the person was on) |
| "Sign in again" | `GET /v1/auth/sign-in?return_to=<to>` | live (top-level navigation) |
| "Privacy · Terms · System status" | — | text only until the firm's policy pages exist (Deviations) |

## Acceptance
- SHL-06 acceptance (P-01 AC 5.1.3): g shows the spinner and "Signing in…" in a live region, refreshes, loads `/v1/me` and opens the safe return path.
- SHL-06 acceptance (AC 5.1.4): an expired session returns to the same route, query included.
- SHL-06 acceptance (AC 5.1.5): no token is kept in `sessionStorage` or `localStorage`.
- SHL-06 acceptance (AC 5.1.6): the build's `connect-src` is `'self'`.
- SHL-06 acceptance: no password field anywhere.

## Figures
None.

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, vendor brand colours or logos, password fields, the words Accrual/Arc, a firm toolbar on this page.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | a–f are not built: the provider hosts them (WorkOS AuthKit, brand-configured) | P-01 §2.2; ADR-141 | P-01 epic |
| DV-2 | g shows "Sign in to Accrued" with the spinner on the primary button, not frame 3's code boxes, checkbox and passkey button | After the hosted pages nothing is typed in the product; the frame keeps the window, wordmark, card and button geometry | DEC-149 |
| DV-3 | The bottom line "Brightwater Hale LLP · US region" is not drawn | The firm and region are unknown until `/v1/me` answers, and the page leaves as soon as it does | DEC-149 |
| DV-4 | The spinner is the 15 px design-system spinner, not 14 | The C-20 spinner comes in 10, 12 and 15 | DEC-149 |
| DV-5 | "Privacy · Terms · System status" are text, not links | No staff policy or status URL exists in configuration yet (Q-01-T41 owns the status page) | DEC-149 |
| DV-6 | With no return path, sign-in lands on `/engagements`, not `/home` | HOME-01 is `planned` until I-01 makes it live; the landing is the same in every environment and is removed with HOME-01 (P-01 R6) | P-01 epic, R6 |
| DV-7 | The hosted a–f may differ from the SHL-06c/e/f copy where AuthKit cannot be configured to match: passkeys, the DEC-35 lockout (3 failed codes → 15 minutes), the 30-day trusted device, forced re-authentication for step-up and monochrome provider buttons are each to be verified on the staging WorkOS environment | P-01 Q2; the in-product T15 (the §2.2 follow-on, proposed for G-02) closes any gap. The provider settings and checks are in `docs/architecture/authkit-staff-sign-in.md` | P-01 Q2; DEC-22, DEC-35 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| g | C (threshold 0.20, maxDiffPixelRatio 3 %) | 0.23 % (local run, 2026-10-23) | manifest `shl-06g.window`; report-only until P-01-T16 locks it |
| error, expired | — | — | undesigned; axe only (`e2e/screens/SHL-06.spec.ts`) |

## Open gaps
- First sign-in of a person with no user row yet (self-serve sign-up SPEC-024, invitation acceptance SPEC-015 and SPEC-024 AC-3): the BFF refuses an unknown provider subject with `unknown_staff_user`, so `/signup`, `/join` and `/client/accept` reach the error state for a brand-new person. The in-browser PKCE flow that let a token exist before the user row did is gone (no token in web storage). Closing it needs a BFF change (a pre-user session for those three routes, or provisioning at the callback), which is identity's: P-08-T10 (portal BFF) for client invitations and a follow-up to P-01-T09 for staff. No backend change is made here.
- The portal pages under `/client` use the same staff auth client until P-08-T11 gives the portal its own `app-core/auth/bff.ts`.
