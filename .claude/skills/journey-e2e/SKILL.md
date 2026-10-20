---
name: journey-e2e
description: Turn one Accrued journey (J01–J28) into Playwright specs — fixture mode first (gated on pull requests), full stack later (nightly) — with axe on every step and the five invariants asserted. Use when a journey's screens reach fixture or live status, or when a change touches a journey.
---

# Journey e2e

## Paths that arrive later
If one of these is missing when this skill needs it, stop and report which one and the task that creates it.
- apps/web/e2e/journeys/ and the assertInvariants helper (arrive with P-08-T16, S6; fixture mode with F-04)

Input: Jnn. Sources: $ACCRUED_BLUEPRINT_DIR/accrued-blueprint/prompts/by-journey/Jnn-*.md (J20–J28 in addendum-waves-5-8),
blueprint §7 step tables, chapter 01 §1.5.1 (when each journey becomes walkable), the screen contracts.

## Conventions
- apps/web/e2e/journeys/Jnn-<slug>.spec.ts; tests named "Jnn <steps>: <outcome>"; long journeys in test.describe.serial
  blocks that share one seeded tenant.
- One spec, two Playwright projects: `fixture` (VITE_FIXTURES, ?as=<persona>, page.clock.setFixedTime) runs on pull
  requests touching the journey's areas; `full` (make dev, make seed-demo, injected clock, fakes for CCH, QBO, NetSuite,
  DocuSign/KBA, M365, Drata) runs nightly and before releases.
- Navigate with to.<ID>() builders or real clicks; raw URLs only for entry points. expectNoSeriousViolations(page) on every step.
- assertInvariants(page, ctx) after every state-changing step:
  INV-1 no sign-off, decision, release, posting, export, envelope send or outbound message has actor kind `agent`;
  INV-2 every agent-set value shows a verified citation or "Uncited";
  INV-3 a walled persona gets the not-allowed state and no data;
  INV-4 a portal persona sees only its scopes;
  INV-5 every state change writes an audit event attributed "<person>", "<person> via Agent" or "Policy: <name> vN".
- A step whose screen is still planned is test.fixme with its epic and chapter 01 date. Never test.skip; never delete a step.

## Steps
1. List the steps and their screens; mark each planned, fixture or live from the manifest.
2. Write the fixture-mode spec for every fixture or live step, with the journey's actors, seed epoch and dates.
3. Add the full-stack variant once those steps' backends are live.
4. make e2e-fixtures (and make e2e for full). Fix flakiness by waiting on state, never on time.
5. Record walkability on the epic issue: "Jnn steps x–y walkable (fixture | full)". Append to the Progress log.

## Never
Assert on pixels (parity is separate); weaken an invariant to pass; let the agent persona use a human-only action except
to assert that it is refused.
