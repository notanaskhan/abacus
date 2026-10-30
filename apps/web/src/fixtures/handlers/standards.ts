// Fixture handlers for C21 part B's reads (K-02-T13; docs/contracts/rules-tables.md): KNW-04 a–h as
// the live routes will answer them (K-02-T08). Drafts are partners' only: anyone else gets the
// list without them and 404 on a draft version (US-3.4). Examples are the registered providers'
// rows, which the live product serves empty until C-01, A-04 and T-08 register them.
import type { StandardOut, StandardVersionOut } from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import {
  EXAMPLES,
  STANDARDS,
  standardDetail,
  standardId,
  standardOut,
  summary,
  versionId,
} from "../seed/standards";

const NOT_FOUND = { detail: "not found" };
const DEFAULT_PERSONA = "priya-raman";

const personaOf = (request: FixtureRequest): string => request.persona ?? DEFAULT_PERSONA;
const byId = (id: string) => STANDARDS.find((s) => standardId(s.key) === id);

export interface StandardsOptions {
  /** No example provider registered: the designed empty state (the live product until C-01). */
  noExamples?: boolean;
  /** K-02-T14 (KNW-04 i): an open draft of one standard, which the owner edits and publishes. */
  draft?: {
    key: string;
    version: number;
    payload: StandardVersionOut["payload"];
    effective?: string;
  };
  /** Another partner saved the draft first: saves and publishes answer 409 `stale_version`. */
  staleOnSave?: boolean;
}

type Draft = NonNullable<StandardsOptions["draft"]> & { rowVersion: number; open: boolean };

export function standardsHandlers(options: StandardsOptions = {}): Record<string, FixtureHandler> {
  const draft: Draft | null =
    options.draft === undefined ? null : { ...options.draft, rowVersion: 1, open: true };
  const withDraft = (out: StandardOut, persona: string): StandardOut => {
    if (draft === null || !draft.open || out.key !== draft.key) return out;
    if (!out.allowed_actions.includes("firm_standard.draft")) return out;
    const def = STANDARDS.find((s) => s.key === draft.key);
    return def === undefined
      ? out
      : { ...out, draft_version: summary(def, draft.version, "draft", null, false) };
  };
  const draftOut = (def: (typeof STANDARDS)[number]): StandardVersionOut => ({
    id: versionId(def.key, draft?.version ?? 0),
    standard_id: standardId(def.key),
    version: draft?.version ?? 0,
    status: "draft",
    effective_from: draft?.effective ?? null,
    payload_schema_version: 1,
    payload_hash: `sha256:${"1".repeat(64)}`,
    change_summary: null,
    drafted_from_version_id: versionId(def.key, def.version),
    drafted_by: def.owner,
    published_by: null,
    published_at: null,
    row_version: draft?.rowVersion ?? 1,
    payload: draft?.payload ?? def.payload,
  });
  return {
    "GET /v1/standards/{standard_id}/versions/{version_id}": (request) => {
      const def = byId(request.params.standard_id ?? "");
      if (def === undefined || draft === null || !draft.open) return json(NOT_FOUND, 404);
      return request.params.version_id === versionId(def.key, draft.version)
        ? json(draftOut(def))
        : json(NOT_FOUND, 404);
    },
    "PATCH /v1/standards/{standard_id}/versions/{version_id}": (request) => {
      const def = byId(request.params.standard_id ?? "");
      if (def === undefined || draft === null) return json(NOT_FOUND, 404);
      if (options.staleOnSave === true) return json({ detail: { code: "stale_version" } }, 409);
      const body = request.body as { payload: StandardVersionOut["payload"] };
      draft.payload = body.payload;
      draft.rowVersion += 1;
      return json(summary(def, draft.version, "draft", null, false));
    },
    "POST /v1/standards/{standard_id}/versions/{version_id}/publish": (request) => {
      const def = byId(request.params.standard_id ?? "");
      if (def === undefined || draft === null) return json(NOT_FOUND, 404);
      if (options.staleOnSave === true) return json({ detail: { code: "stale_version" } }, 409);
      draft.open = false;
      return json({ ...draftOut(def), status: "published", published_by: def.owner });
    },
    "DELETE /v1/standards/{standard_id}/versions/{version_id}": (request) => {
      const def = byId(request.params.standard_id ?? "");
      if (def === undefined || draft === null) return json(NOT_FOUND, 404);
      draft.open = false;
      return json(summary(def, draft.version, "discarded" as never, null, false));
    },
    "POST /v1/standards/{standard_id}/versions": (request) => {
      const def = byId(request.params.standard_id ?? "");
      if (def === undefined) return json(NOT_FOUND, 404);
      if (draft !== null && draft.open) return json({ detail: { code: "draft_exists" } }, 409);
      return json(summary(def, def.version + 1, "draft", null, false), 201);
    },
    "GET /v1/standards": (request) => {
      const kind = request.query.get("kind");
      const items: StandardOut[] = STANDARDS.filter((s) => kind === null || s.kind === kind).map(
        (s) => withDraft(standardOut(s, personaOf(request)), personaOf(request)),
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
        : json(
            (() => {
              const detail = standardDetail(def, personaOf(request));
              const standard = withDraft(detail.standard, personaOf(request));
              return standard.draft_version === null || detail.standard.draft_version !== null
                ? { ...detail, standard }
                : { ...detail, standard, timeline: [standard.draft_version, ...detail.timeline] };
            })(),
          );
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
