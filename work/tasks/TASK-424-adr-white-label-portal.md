---
id: TASK-424
title: "P-08-T30 · ADR P-11 White-label portal, domains, branded email (ADR-163; plan alias ADR-203)"
spec: SPEC-046
acceptance_criteria: [AC-5, AC-6, AC-17]
risk_zone: amber
status: done
epic: P-08
plan_key: P-08-T30
branch: TASK-424-adr-p11-white-label
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"ADR-203 is Accepted before T05 starts, and it records the neutral portal domain without
"accrued", same-origin /v1, the host as a branding hint only, and per-firm DKIM as R-01's."
Draft ADR P-11 from chapter 09 P-11 and DEC-59 (with DEC-01/ADR-133: the portal never shows
"Accrued"), accept it, and record its number.

## Plan (amber zone: docs only)
- Files: `docs/adr/ADR-163-white-label-portal-domains-branded-email.md` (new);
  `docs/adr/README.md` (index row); `docs/adr/backlog.md` (P-11 row and minted list);
  `docs/product/decision-log.md` (DEC-59 artefact).
- No code, migration, registry, flag or matrix edit. Rollback: revert the commit.
- Approval: AMENDMENT-solo §2 and §7 — decided and recorded by the builder; ADR marked Accepted
  with deciders notanaskhan, ayushkbhatia.

## What changed
- **ADR-163** (accepted, amber): two builds on two origins; portal default host
  `<slug>.<neutral-portal-domain>` with a domain that never contains "accrued", read from
  `portal_base_domain`; custom domains in P1 via `portal_domains`; portal routes at the origin
  root; `/v1` same-origin on every host; the host is a branding hint only, sessions pinned to
  tenant and host; one Public branding surface (`/v1/portal/branding` and `/branding/logo`) on the
  ROUTE-001 exception list owned by ADR-152; branding as slots with "Secured by Accrued" off by
  default; branded email through SES in the firm's name, per-firm DKIM and sender-domain lifecycle
  owned by R-01, neutral mail-domain fallback with the firm's Reply-To; options A–E; enforcement
  (L7 lint, host-pinning test, branding contract test, domain config check, portal bundle check).
- **Numbering.** The plan's "ADR-203" is a plan alias; the next free number on `main` was
  ADR-163. `backlog.md` records "ADR-163 (plan alias ADR-203)", status accepted, epic P-08, and the
  minted list gains "P-11 = ADR-163".
- **Decision log.** DEC-59's artefact now links ADR-163 and names ADR-152 (P-45, proposed).

## Decisions taken in the session
- Per-firm DKIM and the sender-domain lifecycle are R-01's (ADM-10, POR-20) over Q-01's SES
  setup, as the P-08 row requires; the ADR records the neutral mail-domain fallback from chapter 06
  §1.11 so client email never says "Accrued" before a firm verifies its domain.
- Host pinning (chapter 04 §1.3 "inferred") is made binding: a portal session on another host is
  answered as no session (P-08 Story 1.2).
- `/v1/portal/branding/logo` belongs on the P-45 exception list; ADR-152 is still proposed, so the
  ADR names it as follow-up for ADR-152 before acceptance (P-08 OQ-2) rather than editing ADR-152
  here.

## Progress log
- 2026-10-23: drafted from chapter 09 P-11, DEC-59, X-12, DEC-01/ADR-133, chapter 03 §12.2–12.3,
  chapter 04 §1.3, chapter 06 §1.11–1.12 and P-08 §0.1/§3.1. Checks: `validate_docs`,
  `banned_patterns`.
