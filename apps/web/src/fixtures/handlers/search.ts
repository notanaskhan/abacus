// C15 v1 in fixture mode (P-02-T11; docs/contracts/c15-search.md): `POST /v1/search` and the
// recents routes on the SHL-02 seed (seed/shl02.ts). The search text arrives in the body only.
import type { FixtureHandler } from "../../app-core/fixture-mode";
import { json } from "../../app-core/fixture-mode";
import { SHL02_B_RECENTS, SHL02_C, resultsFor } from "../seed/shl02";

export function searchHandlers(walled = false): Record<string, FixtureHandler> {
  return {
    "POST /v1/search": ({ body }) => {
      const { q, types } = body as { q: string; types?: string[] | null };
      if (types?.length === 1 && types[0] === "agents" && q === "") return json(SHL02_C);
      return json(resultsFor(q, walled));
    },
    "GET /v1/search/recents": () => json(SHL02_B_RECENTS),
    "POST /v1/search/recents": ({ body }) => json(body),
  };
}
