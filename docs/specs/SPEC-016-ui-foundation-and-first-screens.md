---
id: SPEC-016
title: UI foundation (direction C, "Atelier") and the first screens
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-011, ADR-013, ADR-065, ADR-024, ADR-030]
related_specs: [SPEC-008, SPEC-013, SPEC-015, SPEC-004]
created: 2026-10-08
updated: 2026-10-08
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
The founder chose visual direction **C, "Atelier"** (see the UX brief and directions canvas) and asked for the spec to be written and built without further mockups. This spec covers:
- **The foundation:** design tokens and a small component set in `packages/ui`, so every screen shares one look.
- **The firm app shell:** an icon rail, a header with the firm switcher, a notification bell and panel, and a fresh-MFA prompt.
- **The first screens:** engagement overview, engagement map, client contacts, methodology templates, and the client's accept-invitation page and home.
- **The existing screens** (engagements list, evidence board, review) restyled to the tokens, with their behaviour unchanged.

## 2. Problem and context
The SPA has five basic components with no tokens and no shared shell. The backend now serves:
- the engagement graph;
- notifications;
- client invitations and contacts;
- methodology templates.

None of these has a screen yet.

## 3. Actors
Firm staff (partner, manager, senior, staff, reviewer), firm admins and practice leaders, and client admins and contributors (SPEC-015).

## 4. Goals and non-goals
**Goals**
- **Tokens (direction C)**, as CSS custom properties under `@theme` in `packages/ui/src/theme.css`, imported by the app. Light only at launch (§20).

  | Token | Value | Use |
  |---|---|---|
  | `--color-ground` | `#F6F4F0` | page background |
  | `--color-surface` | `#FFFDFA` | panels, cards, tables |
  | `--color-rail` | `#EFEBE4` | icon rail, quiet headers |
  | `--color-sunken` | `#F1EDE6` | table header, avatars, neutral pills |
  | `--color-ink` | `#23201C` | text |
  | `--color-muted` | `#5F5850` | secondary text (≥4.5:1 on ground and surface) |
  | `--color-line` | `#E2DCD2` | borders |
  | `--color-accent` | `#7A4E12` | primary actions, links, selection |
  | `--color-accent-soft` | `#F3E8D6` | selected rows and areas |
  | `--color-ok`, `--color-ok-soft` | `#24502A`, `#E6EFE6` | received, accepted, ready |
  | `--color-warn`, `--color-warn-soft` | `#7A3B0B`, `#F7E6D5` | needs revision, gaps |
  | `--color-info`, `--color-info-soft` | `#4E3470`, `#EDE6F4` | in progress, fieldwork |
  | `--color-danger`, `--color-danger-soft` | `#8A1C1C`, `#F8E3E1` | errors, rejected |
  | `--color-ai`, `--color-ai-line` | `#5E3F86`, `#C9B6DE` | the AI tag |
  | radii | 8 px controls, 12 px panels | |
  | type | Source Sans 3 (body 15 px, small 13 px), Newsreader 500/600 (page and section headings), tabular figures (`font-variant-numeric: tabular-nums`) | |

  Status is never shown by colour alone: every pill carries a word.
- **Fonts self-hosted:** `@fontsource/source-sans-3` and `@fontsource/newsreader`, added to the dependency allowlist. This is needed because the production Content-Security-Policy (`default-src 'self'`) blocks remote fonts.
- **Components** (`packages/ui`), restyled or new:
  - Button (primary, outline, ghost), Badge (tones ok, warn, info, danger, neutral), Card;
  - `StatusPill`, `AiTag` (the AI label plus a citation count link), `Count` (done of total, tabular);
  - `Tabs` (links), `Rail` and `RailItem` (icon plus label, an optional badge);
  - `Panel` (a side panel with a heading);
  - `DataTable` (header row, rows, an empty state, a horizontal-scroll wrapper);
  - `Field` and `Select`, Dialog, `Toast`.

  All keyboard-accessible, with visible focus, labels on icon-only buttons, and 44 px minimum touch targets on the rail.
- **The firm shell** (`Layout`):
  - **The rail:** Engagements · Review queue (when inside an engagement) · Knowledge (placeholder link, a later screen) · Firm admin (shown for firm admins and practice leaders) · Notifications (with an unread badge) · Account (sign out).
  - **The header:** breadcrumbs, the engagement status, and the firm switcher for users in several firms.
  - **The notification panel:**
    - the newest 50, with the unread count;
    - each item rendered from its kind's template (SPEC-013) and linked to its subject;
    - mark one read, and mark all read;
    - polled every 60 seconds and on focus.
  - **Fresh-MFA prompt:** when an MFA-required action answers 403 and the session's MFA is stale, a dialog ("Confirm it's you") re-runs sign-in with a forced login and returns to the same page.
- **Engagement pages** under `/engagements/$id`, with tabs Overview · Requests (the existing board) · Map · Contacts, and Review reached from the board and the rail.
  - **Overview** (from the graph):
    - **left:** audit areas with done-of-total (items whose status isn't open, over all items) and gap tags;
    - **centre:** the selected area's request items (status, tier, latest evidence, the screening action with `AiTag`);
    - **right:** coverage gaps (counts linking to the map), screening counts (ready for review, needs revision, not screened), and a team summary.
    - With no methodology pinned, a "Apply a methodology template" call to action (managers and partners).
  - **Map:** each area as a section listing its accounts (code, name, balance) beside its request items. Unmapped accounts and empty areas sit in a highlighted "Gaps" section at the top.
  - **Contacts** (SPEC-015):
    - client members and pending invitations;
    - "Invite client contact" (email and role; the role list limited for client admins by the API's answer);
    - resend, revoke and remove, each confirmed in a dialog.
    - The link is never shown.
- **Firm admin**, under `/admin`: **Methodology**.
  - Lists templates and versions; a version opens its areas, requests and account rules.
  - **"Upload version":** pick a template name and an `.xlsx` file, sent as the raw body (SPEC-008 D3), with fresh-MFA handling. Upload errors are shown as a table of sheet, row, column and a plain-language message for each code.
  - Apply to an engagement happens from the engagement overview (a version picker).
- **The client route tree** under `/client` (ADR-011: separate from the firm's):
  - **`/client/accept`:**
    1. reads `#token=` from the URL fragment, keeps it in `sessionStorage` only until it is used, and removes it from the address bar;
    2. signs in (passwordless at the identity provider);
    3. posts the acceptance;
    4. shows success, or one neutral failure message for every failure (SPEC-015 AC-5);
    5. then goes to the client home.
  - **`/client`:** the firms and engagements the client belongs to (from `/v1/me` memberships of kind `client`). The engagement page is a shell, "Your auditor will share requests here", until increment 2. Signed-in client users who land on firm routes are redirected to `/client`, and staff who land on `/client` go to `/`.
- **Restyle** the engagements list, the evidence board and review to the tokens and shell, with no behaviour change.

**Non-goals**
- Mockups of the other screens (the founder waived them).
- Dark mode.
- Knowledge, budget, support-session and walls screens (later UI tasks).
- Client uploads and connections (increment 2).
- A staff console.
- New backend APIs, except where §8 notes a gap.

## 5. User stories and acceptance criteria
- **AC-1** Given any screen, then colours, type, radii and spacing come only from the tokens: no raw hex values in `apps/web` (an ESLint rule bans hex colour literals and arbitrary Tailwind colour values outside `packages/ui/src/theme.css`).
- **AC-2** Given the shell, then the rail, header, firm switcher and notification bell are on every firm page. The bell shows the unread count, the panel lists notifications with readable text, and marking read updates the count.
- **AC-3** Given an engagement with a pinned methodology, when its overview opens, then areas show done-of-total, the selected area's items show status and screening (AI-tagged with citations), and coverage gaps and screening counts match the graph.
- **AC-4** Given the map, then unmapped accounts with balances and areas with no requests appear first, under Gaps. Every account shows its code, name and right-aligned tabular balance.
- **AC-5** Given a partner or manager, when they invite a client contact, then the contact list shows the pending invitation (email, role, expiry) and never a link. Resend, revoke and remove ask for confirmation and update the list.
- **AC-6** Given a firm admin, when they upload a valid workbook, then the new version appears. With an invalid one, each problem shows its sheet, row and column and a message. If MFA is stale, the confirm dialog appears, and after re-sign-in the upload can be retried.
- **AC-7** Given an invitation link, when the client opens it, signs in and accepts, then they land on their client home. A used, expired or wrong link shows one neutral message. The token never stays in the address bar or in `localStorage`.
- **AC-8** Given a client user on a firm route, then they're sent to `/client`, and firm navigation is never shown to them.
- **AC-9** Given model text anywhere (screening rationale), then it is rendered only through `AgentText` (OUT-001), with the `AiTag` beside it.
- **AC-10** Given every new screen, then axe reports no WCAG 2.2 AA violations, every interactive element is reachable by keyboard, and loading, empty, error and not-allowed states exist.

## 6. Behaviour and flows
**Partner:**
1. engagements;
2. engagement overview;
3. apply a methodology (version picker);
4. the request list fills;
5. Contacts → invite the client;
6. Map → close the gaps.

**Client:**
1. the email link;
2. accept;
3. sign in;
4. client home.

**Admin:**
1. Firm admin → Methodology;
2. upload;
3. fix row errors;
4. re-upload.

## 7. Domain and data changes
None. One frontend dependency pair is added (fonts), which is a protected allowlist change.

## 8. Interfaces
Uses existing APIs only:
- `/v1/me`;
- `/v1/notifications*`;
- `/v1/engagements*` (graph, client-contacts, client-invitations, methodology apply, request-items);
- `/v1/methodology/*`;
- `/v1/invitations/accept`.

**Known gap:** the methodology upload's body isn't typed in OpenAPI (SPEC-008 D3). The app sends it through the generated client's raw-body option. It never calls `fetch` directly (the ESLint ban on `fetch` outside the API client stands).

## 9. Authorisation and tenancy
The UI hides what the API would refuse, using the role from `/v1/me` and each list's responses, but the backend remains the only authority (ADR-011). Client and firm route trees are separate.

## 10. AI behaviour
None new. Model text goes only through `AgentText`, beside an `AiTag`.

## 11. Integrations
The identity provider for sign-in and forced re-login (fake OIDC locally).

## 12. Edge cases and failure modes
- **An engagement with no graph data** (no snapshot, no template): an empty state with the next step.
- **A user with many firms:** the switcher. Notifications are per active firm.
- **A notification about something the user can no longer see:** the API already hides it.
- **An expired session during an upload:** the existing 401 handling re-signs in.

## 13. Security and privacy
- **Invitation tokens:** they live only in the URL fragment and, briefly, in `sessionStorage`, cleared on use or failure, and are never logged.
- **No remote assets:** fonts are bundled, so the CSP is unchanged.
- **Model text is plain text only** (`AgentText`).

## 14. Audit trail and evidence integrity
None.

## 15. Observability
Unchanged (the existing error tracking).

## 16. Performance and scale
Code-split routes per area (firm admin, client), and lists paginated by the API where offered.

## 17. UX
As specified above. The directions canvas (C) is the visual reference.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | lint | The no-raw-colours rule, with a lint test |
| AC-2 to AC-8 | component (vitest, Testing Library) with a mocked client | Shell, bell, overview, map, contacts, upload errors and MFA prompt, accept flow, client redirect |
| AC-9 | component and existing OUT-001 | Model text through `AgentText` |
| AC-10 | Playwright with axe on key pages (with the founder's full runs later) | Accessibility |

## 19. Rollout
Behind no flag; the SPA has no external users yet.

## 20. Open questions
None. Decided by the founder on 2026-10-08: direction C; no further mockups; build. Defaults taken here and open to change:
- **Theme:** light only at launch.
- **Logo:** the wordmark is a text placeholder ("Abacus" in Newsreader) until a logo exists.
- **Fonts:** bundled through `@fontsource` (an allowlist addition).

## 21. Future / explicitly deferred
- Dark theme.
- Knowledge, budget and spend, support access, and walls screens.
- Notification email.
- The client portal's content (increment 2).
- A logo.
