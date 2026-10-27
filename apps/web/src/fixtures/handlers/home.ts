// `GET /v1/home` in fixture mode (I-01-T05; the C13 home half): the persona's HomeVM from
// seed/home.ts, narrowed to an office when `office_id` names one (DEC-30: a filter). A client
// principal never reaches it in the firm bundle. Typed with the generated client.

import type { HomeOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import { homeView } from "../seed/home";
import { OFFICES } from "../seed/people";
import { officeIdOf } from "../seed/shell";

export function homeHandlers(
  view: (persona: string, office: (typeof OFFICES)[number]["name"] | null) => HomeOut = homeView,
): Record<string, FixtureHandler> {
  return {
    "GET /v1/home": (request) => {
      const id = request.query.get("office_id");
      const office = OFFICES.find((o) => officeIdOf(o.name) === id)?.name ?? null;
      return json(view(request.persona ?? DEFAULT_PERSONA, office) satisfies HomeOut);
    },
  };
}
