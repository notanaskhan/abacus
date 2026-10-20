---
id: ADR-155
title: packages/ui is the Accrued design system - Tailwind v4 tokens, self-hosted fonts, Radix for behaviour, the AA ink ladder
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
The repo's first UI ("Atelier", SPEC-016) was built on shadcn/ui defaults. The Accrued handoff defines its own design language: greige surfaces, espresso ink on an alpha ladder, Geist at 400 and 500, pills, hairline rings. TASK-091 to TASK-101 already moved the live screens onto the plan's tokens. The handoff's ink ladder fails WCAG 2.2 AA for small text, and the plan records the AA values (DEC-11). This is P-03 (DEC-04, DEC-11, DEC-15).

## Decision
`packages/ui` is the Accrued design system and the only place visual values are defined:
1. **Tokens** live in Tailwind v4 `@theme` in `packages/ui/src/theme.css` (a typed `tokens.ts` mirror arrives with F-05-T03). Tailwind's default palette and shadows are reset (`--color-*: initial`, `--shadow-*: initial`), so only plan tokens compile; type sizes stay mapped onto the plan's roles until the F-05-T06 codemod.
2. **Fonts** are self-hosted through Fontsource: Geist and Geist Mono (UI), Arimo (metric fallback), Gelasio (statements and letters). The CSP blocks remote fonts.
3. **Radix** provides behaviour only; styling comes entirely from tokens.
4. **Light theme only**, with `forced-colors` support: focus is an outline, never only a box-shadow.
5. **AA ink ladder** (DEC-11): ink-2 text at .70, ink-3 text at .66, match text `#7E4590`, focus outline `2px solid rgba(43,31,23,.55)`. The handoff's lighter values are used only for parity runs under `data-contrast="reference"`. SPEC-016 AC-10's axe gate stays.
6. **Precedence** for any screen: `revision.md` over `spec.md` over the kit.
7. **Controls are pills** (`--radius-pill`; DEC-109).
8. Every token change adds a line to `packages/ui/src/tokens/DECISIONS.md`.

## Options considered
### Option A: the plan's tokens in packages/ui, AA ladder — chosen
- Pros: one source of truth; screens already moved (TASK-091..101); accessible by default.
- Cons: the reset needs a codemod for the remaining Tailwind type utilities (F-05-T06).

### Option B: keep shadcn defaults and theme them
- Pros: less churn.
- Cons: two design languages; defaults leak into new screens; parity with the handoff impossible.

## Consequences
- **Code:** `theme.css` resets default colours and shadows (done in SU-24); `tokens.ts` mirror and `root.css` with F-05-T03; codemod of `text-*` utilities with F-05-T06 (S0-S1); `/components` gallery replaces `/_ds` in F-05-T09.
- **Specs:** SPEC-048 supersedes SPEC-016 §4; SPEC-016 is otherwise unchanged.
- **Tests:** `apps/web/src/lint/tokens.test.ts` checks the ladder, contrast on every surface, match text, focus outline, the reset and the body.
- **Open:** the plan's body line height is 15.6px (1.2); the app ships 1.45. Changing it moves every screen, so it is decided in F-05-T05 by the builder.

## Enforcement
`tokens.test.ts` (Vitest), the ESLint literal-colour rules, axe in the e2e journey and `/components`, and `DECISIONS.md` for every token change.

## Guidance for agents
Use plan tokens only (`bg-card`, `text-ink-2`, `shadow-pop`); never a Tailwind palette colour, a literal colour or a default shadow. Never lower an ink alpha below the ladder.

## Revisit when
A dark theme or a second product surface is planned.

## Related
P-03; DEC-04, DEC-11, DEC-15, DEC-109, DEC-115. Supersedes only ADR-011's "shadcn as the base" clause. SPEC-016, SPEC-048.
