---
id: TASK-388
title: app-core session hooks and the role-literal lint (F-03-T32)
spec: SPEC-024
acceptance_criteria: [AC-5]
risk_zone: green
status: done
epic: F-03
plan_key: F-03-T32
branch: f03-t32-session-hooks
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"A misspelt action name is a type error, and a new role-literal comparison in screens fails
lint." (ADR-145; plan 04, section on capabilities)

## What changed
- `apps/web/src/app-core/session.ts`: `useSession(scope?)` joins `/v1/me` and
  `/v1/me/capabilities` (user, active tenant membership, memberships, roles with labels, flags,
  entitlements, office, tz, `mfaRecentUntil`, `serverNow`, portal, status). `MODULES` / `Module`
  mirror `platform.entitlements.Module`; `useCapabilities(scope?)` is the shared read.
- `app-core/can.tsx`: `useCan(action: Action, { engagementId? })` and `<Can action engagementId
  fallback>`. An engagement scope sends `engagement_id`; each scope has its own query key.
- `app-core/flags.tsx`: `useFlag(name)` (boolean or variant value), `useEntitlement(module)`,
  `<FeatureGate flag [value] | entitlement fallback>` (flag and entitlement are exclusive in the
  type).
- Every check is false while capabilities load or after they fail (fail closed).
- ESLint (`apps/web/eslint.config.js`): `ROLE_SYNTAX` refuses `===`/`!==`/`==`/`!=` against a
  role-code literal, `case "<role>":`, `.includes("<role>")` and `["<role>", …].includes(x)`, in
  every `src/**` file except tests, `src/app-core/**` and `src/legacy/**` (M2 replaces legacy; its
  checks move with P-01's codemod). A comparison on a `.kind` (membership kind "staff") is not a
  role and is allowed. The new block repeats `SCREEN_SYNTAX` and `NEW_CODE_SYNTAX`, since flat
  config replaces `no-restricted-syntax` options per block.
- The cross-feature import ban (`../../*`) is now a regex that admits `app-core` at any depth:
  plan 04's boundaries let every feature import `app-core/*`, and the old glob refused it from
  `src/routes/firm/`.
- `routes/firm/settings.tsx`: the one role comparison outside legacy (`firm_role ===
  "firm_admin"` for autonomy) is now `useCan("autonomy_policy.update")`; the matrix grants it
  to the firm admin only, and capabilities exclude fresh MFA, so behaviour is unchanged.
- `testing/support.tsx`: `Call.query` (the request's search params) so tests can see
  `engagement_id`.
- Tests: `app-core/session.test.tsx` (useCan true/false/loading/error, engagement scope,
  `<Can>` and `<FeatureGate>` fallbacks, useFlag/useEntitlement, useSession; `@ts-expect-error`
  on a misspelt action, a bogus module and a flag+entitlement gate, so `tsc` fails if one ever
  compiles). `lint/eslint-rules.test.ts`: refused in `src/routes/x.tsx` and a screen, allowed in
  `src/app-core/x.ts` and `src/legacy/x.tsx`, kind comparisons allowed, app-core importable.

## Progress log
- 2026-10-22: built. Ran tsc, eslint, prettier and the two touched test files; the rest runs in
  the batch's end-of-run CI.
