---
name: frontend-feature
description: How to build a frontend screen or component — design system, generated API client, states, accessibility. Use for any web app work.
---

# Frontend feature pattern

**Reference:** `docs/architecture/reference/frontend-feature.md` (from the walking skeleton's evidence board).

## Rules
- Call the backend only through `packages/api-client` (generated); never `fetch` directly (ADR-011, 013).
- Use components from `packages/ui`; extend the design system rather than styling one-offs.
- Handle empty, loading, partial, error and success states.
- Render agent-generated text only through the sanitised plain-text component (ADR-065).
- Never hide security behind the UI; the backend enforces permissions.
- Keyboard accessible and labelled; Playwright journeys include accessibility checks.
- Glossary terms in identifiers; UI labels may use friendlier wording defined in the spec.
