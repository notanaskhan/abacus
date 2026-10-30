// C21 reference sets in fixture mode (K-02-T17; KNW-04 j): the list by kind, a set resolved as of a
// date (the one published version each set holds here) and its versions. Read-only, as the routes
// are for every firm role.
import type { FixtureHandler } from "../../app-core/fixture-mode";
import { json } from "../../app-core/fixture-mode";
import { REFERENCE_SETS, REFERENCE_SET_VERSIONS } from "../seed/reference-sets";

const NOT_FOUND = { detail: "not_found" };

export function referenceSetsHandlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/reference-sets": (request) => {
      const kind = request.query.get("kind");
      const items = REFERENCE_SETS.filter((s) => kind === null || s.kind === kind);
      return json({
        items,
        next_cursor: null,
        total: items.length,
        total_capped: false,
        counts: {},
        facets: {},
      });
    },
    "GET /v1/reference-sets/{key}": (request) => {
      const key = request.params.key ?? "";
      const set = REFERENCE_SETS.find((s) => s.key === key);
      const version = REFERENCE_SET_VERSIONS[key];
      if (set === undefined || version === undefined) return json(NOT_FOUND, 404);
      return json({ as_of: request.query.get("as_of") ?? version.effective_from, set, version });
    },
    "GET /v1/reference-sets/{key}/versions": (request) => {
      const version = REFERENCE_SET_VERSIONS[request.params.key ?? ""];
      return version === undefined
        ? json(NOT_FOUND, 404)
        : json({
            items: [version],
            next_cursor: null,
            total: 1,
            total_capped: false,
            counts: {},
            facets: {},
          });
    },
  };
}
