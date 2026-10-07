# Reference: a frontend feature

The pattern every screen copies (SPEC-000 §22), from the walking skeleton's evidence board (TASK-012). Binding rules: ADR-011, ADR-013, ADR-065, ADR-077, ADR-083.

## Data: the generated client only

```tsx
import { listRequestItemsOptions, listRequestItemsQueryKey } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";

const items = useQuery(listRequestItemsOptions({ path: { engagement_id: engagementId } }));
```

- **Calls:**
  - Every backend call goes through `@abacus/api-client`, generated from the API's OpenAPI (`make generate`).
  - `@abacus/api-client/query` gives TanStack Query `…Options`, `…Mutation` and `…QueryKey` helpers.
  - ESLint bans `fetch`, `XMLHttpRequest` and `axios` elsewhere. The one exception is the identity provider's token endpoint in `src/auth/session.ts`.
- **Configuration** (`src/api.ts`): the client is configured once, with the same-origin base URL, the bearer token, `X-Abacus-Tenant` when a user picks a firm, and sign-in again on 401. Screens never handle tokens.
- **After a mutation:** invalidate the queries it changes, by their generated `…QueryKey`.
- **Joining data:**
  - Join data from several modules in the screen, not in the API. The board joins request items, evidence versions and screening results on `evidence_version_id` (`src/board/join.ts`), because module boundaries forbid one endpoint reading all three.
  - Keep joins as pure functions with unit tests.
- **Types:** the client's sources are generated and type-checked through their declarations (`packages/api-client/dist`, built by `make setup` and `make generate`). Never edit `src/`.

## Components: the design system only

- **Primitives:** build from `@abacus/ui`: Button, Input, Label, Card, Table/Th/Td, Badge, Dialog, Alert, Skeleton, Spinner, EmptyState. These are shadcn-style primitives on Radix with Tailwind defaults. A missing component is added to `packages/ui`, not styled once in a screen.
- **Model output** (rationale, quotes, unverified notes) is untrusted:
  - render it only with `<AgentText text={…} />`, which renders plain text, strips control, bidirectional and invisible characters, and caps the length (ADR-065);
  - ESLint fails `dangerouslySetInnerHTML` anywhere, and `.rationale`/`.quote` rendered outside `AgentText`.
- **Agent proposals:** label them as proposals ("Agent proposes: …"). No screen offers to accept or confirm one; agents propose, humans decide (ADR-005).

## States

Every data view handles each state explicitly:

| State | Show |
|---|---|
| Loading | `Skeleton` (`aria-busy`) or `Spinner` with a label |
| Empty | `EmptyState` with the next action |
| Partial | What exists, with progress for the rest (the board's "Screening…" while evidence awaits its proposal; polling stops when nothing is pending) |
| Error | `Alert` with Retry; `errorMessage()` shows only short server `detail` strings |
| Success | The data |

## Accessibility

- **Labels:** give every input a `Label`, every icon `aria-hidden`, and every status change a `role="status"` element (Spinner).
- **Dialogs:** use the design-system `Dialog`, which has a focus trap and a title.
- **Checks:** the Playwright journey runs axe on each screen and fails on serious or critical violations.

## Sign-in

- **Flow:** OIDC authorization code with PKCE (`src/auth`).
  - Locally the provider is `abacus_tools.fakes.oidc_server`: `make dev` runs it, and `make seed` creates its dev users and connects engagements to the fake connector.
  - In staging it is WorkOS (TASK-014).
- **Tokens:** they live in `sessionStorage` for this tab only. An expired token means signing in again; there are no refresh tokens yet (ADR-030).

## Tests

- **Unit:** Vitest and Testing Library for components, joins and auth helpers. Mock the network through the generated client's `fetch`, never real HTTP.
- **Journey:** one Playwright journey per spec, with axe (`apps/web/e2e`). `make e2e` runs it against `make dev`; CI runs it nightly (`.github/workflows/e2e.yml`, stage 5).
