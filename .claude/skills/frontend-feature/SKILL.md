---
name: frontend-feature
description: How to build a frontend screen or component — design system, generated API client, states, accessibility. Use for any web app work.
---

# Frontend feature pattern

**Reference:** `docs/architecture/reference/frontend-feature.md` (from the walking skeleton's evidence board).

## Rules
- Call the backend only through `packages/api-client` (generated); never `fetch` directly (ADR-011, 013). Use `@abacus/api-client/query` helpers with TanStack Query; invalidate by the generated `…QueryKey` after mutations.
- Use components from `packages/ui`; extend the design system rather than styling one-offs.
- Handle empty, loading, partial, error and success states.
- Render agent-generated text only through `<AgentText text={…} />` from `@abacus/ui` (ADR-065); ESLint enforces it and bans `dangerouslySetInnerHTML`.
- Join data from several modules in the screen with pure, unit-tested functions (see `apps/web/src/board/join.ts`); don't ask for cross-module endpoints.
- Never hide security behind the UI; the backend enforces permissions.
- Keyboard accessible and labelled; Playwright journeys include accessibility checks (`@axe-core/playwright`), run by `make e2e` and nightly in CI.
- Tests: Vitest + Testing Library, network mocked through the generated client's `fetch`.
- Glossary terms in identifiers; UI labels may use friendlier wording defined in the spec.
