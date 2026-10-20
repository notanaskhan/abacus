---
name: portal-screen
description: Rules that apply on top of build-screen-from-handoff for any screen or component of the white-labelled client portal (POR-*, T7 and T7-M, the portal T15 sign-in, T16 signing) — branding by host, role-union shells, scoped read models, three widths, and no "Accrued" anywhere. Use for every POR-* screen and portal component.
---

# Portal screen

## Paths that arrive later
If one of these is missing when this skill needs it, stop and report which one and the task that creates it.
- GET /v1/portal/branding and the portal entry (arrive with R-01, S7–S18)
- the white-label crawler (arrives with R-01)

Use together with build-screen-from-handoff. The portal is its own Vite entry (portal.html) on its own origin: a neutral
portal domain plus firm custom domains (DEC-59), same-origin /v1.

## Rules
1. Branding comes from GET /v1/portal/branding. The host is a hint; the tenant comes from the session. Firm name, logo and
   colours stay inside the token ladder; "Secured by Accrued" is off by default (DEC-15).
2. No "Accrued" in copy, titles, alt text, meta tags, client-side strings, error pages or bundle strings. The white-label
   crawler fails the build on any hit.
3. Shells come from /v1/me (portal.shell) by role union (blueprint §2.3). One person may hold several grants; the union
   decides the tabs. Third parties (link principals) see only their room.
4. Data only from portal read models (the `portal` module); never import firm shell code or firm domain hooks.
   `scope_only` grants hide everything else. Scopes that need MFA (tax return information, signing, approving) show the
   step-up state, never the data.
5. Render and test at 1400, 720 and 390; mobile uses the bottom tab bar (DEC-15); parity on the -M crops.
6. Client copy uses plain words, never internal status codes. Model-drafted text never reaches a client unless ADR P-25's
   conditions hold for that firm (off by default). Code-rule matches read "Suggested — <Firm> will confirm" (DEC-58).
7. Client actions that decide something (sign, approve, withdraw an unaccepted upload) are explicit buttons with a
   confirmation, never automatic.
8. Emails are database templates rendered by the backend (contract C16); a screen never composes email.

## Tests
INV-4 in every scenario: a second client persona and a third party cannot see each other's data. axe at all three widths.
The white-label crawler on every state.
