// Fixture handlers for C21 part B's reads (K-02-T13; docs/contracts/rules-tables.md): KNW-04 a–h as
// the live routes will answer them (K-02-T08). Drafts are partners' only: anyone else gets the
// list without them and 404 on a draft version (US-3.4). Examples are the registered providers'
// rows, which the live product serves empty until C-01, A-04 and T-08 register them.
import type { StandardOut } from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { EXAMPLES, STANDARDS, standardDetail, standardId, standardOut } from "../seed/standards";

const NOT_FOUND = { detail: "not found" };
const DEFAULT_PERSONA = "priya-raman";

const personaOf = (request: FixtureRequest): string => request.persona ?? DEFAULT_PERSONA;
const byId = (id: string) => STANDARDS.find((s) => standardId(s.key) === id);

export interface StandardsOptions {
  /** No example provider registered: the designed empty state (the live product until C-01). */
  noExamples?: boolean;
}

export function standardsHandlers(options: StandardsOptions = {}): Record<string, FixtureHandler> {
  return {
    "GET /v1/standards": (request) => {
      const kind = request.query.get("kind");
      const items: StandardOut[] = STANDARDS.filter((s) => kind === null || s.kind === kind).map(
        (s) => standardOut(s, personaOf(request)),
      );
      return json({
        items,
        next_cursor: null,
        total: items.length,
        total_capped: false,
        counts: {},
        facets: {},
      });
    },
    "GET /v1/standards/{standard_id}": (request) => {
      const def = byId(request.params.standard_id ?? "");
      return def === undefined
        ? json(NOT_FOUND, 404)
        : json(standardDetail(def, personaOf(request)));
    },
    "GET /v1/standards/{standard_id}/examples": (request) => {
      const def = byId(request.params.standard_id ?? "");
      if (def === undefined) return json(NOT_FOUND, 404);
      const examples = options.noExamples === true ? undefined : EXAMPLES[def.key];
      return json(
        examples === undefined
          ? {
              standard_id: standardId(def.key),
              period: request.query.get("period"),
              provider_registered: false,
              caption: null,
              rows: [],
            }
          : { standard_id: standardId(def.key), ...examples },
      );
    },
  };
}
