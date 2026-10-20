---
name: ui-kit-component
description: Port one design-system kit, template or overlay (C-00…C-39, T1–T22, O1–O6) from the handoff into packages/ui — typed props, forceState, a specimen for every state, the gallery page, tests and the parity tier. Use when a screen needs a component with no merged specimen; never inside a screen task.
---

# Port a kit into packages/ui

## Paths that arrive later
If one of these is missing when this skill needs it, stop and report which one and the task that creates it.
- packages/ui/src/tokens/DECISIONS.md (arrives with F-05-T01, S0)
- the /components specimen gallery's parity tiers (arrive with F-05)

Input: KIT (for example C-16 Request, T1 Index list, O3 Dialog). Sources: $ACCRUED_HANDOFF_DIR/handoff/kits.md (the kit's
section), kits/<Kit>.dc.html (grep the part; read renderVals for derived values), handoff/canvases/Component Sheet.md,
design-tokens.md, packages/ui/src/tokens/DECISIONS.md.

## Layer rules
- L1 primitives and templates: Radix for behaviour only, styled 100% with tokens, no domain words, `forceState` on every
  interactive component. Templates T1–T22 and O1–O6 are typed layout components sharing ViewState.
- L2 kits: generic data shapes in the component's own types.ts (never @abacus/api-client types); data in through props,
  intents out through callbacks; no API calls; renders from fixtures with no backend.

## Steps
1. Read the kit section, its props and every state the Component Sheet shows; list the states.
2. Conflicts: a built kit wins over 02-design-system A8 (DEC-15). Any other conflict → one line in tokens/DECISIONS.md;
   stop if it would change a token (tokens are ayushkbhatia's).
3. Write <Kit>/types.ts, <Kit>.tsx, <Kit>.specimens.tsx (one specimen per state, ids like "C-16.b") and <Kit>.test.tsx
   (behaviour, keyboard, forceState, "…" on dialog openers, HumanAction refusing agent actors where relevant).
4. Tokens only; Geist 400/500; hairlines; no blur; numbers through format.ts; status through StatusPill object + code;
   agent text through AgentText.
5. Export one sorted line in packages/ui/src/index.ts and specimens.ts, only now that a specimen exists.
6. Gallery: /components/c/<kit> (or /components/templates/<T>) renders every specimen; axe 0 serious or critical; keyboard works.
7. Parity: tier A for primitives and chrome strips; tier B for templates (blocking once parity-locked); tier D computed-style
   assertions for template geometry (chapter 04 §9.3).
8. make check; append to the Progress log; commit on a short branch and merge once green.

## Never
Import from apps/web or the API client; add a dependency outside the allowlist (ask for the sprint bundle); add a literal
colour or size; build a screen in this task.
