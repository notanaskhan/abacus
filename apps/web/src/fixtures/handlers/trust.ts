// C4 fixture handlers (P-03-T07): the citations and viewer routes over a scenario's records, in
// the shapes the OpenAPI document gives them. Lists filter as the server does (DEC-265: an anchor's
// stack by `n`; `host_ref` is `<anchor_type>:<anchor_id>`); an unknown id is 404, as a walled one
// is. Page images are the synthetic PNGs, `no-store` like the server's.

import type {
  CitationV2Out,
  EvidenceUnlockOut,
  ListPageCitationV2Out,
  PiiRevealOut,
  ViewerRegionsOut,
  ViewerSearchOut,
  ViewerTextOut,
} from "@abacus/api-client";
import { FORM_PAGE_PNG, STATEMENT_PAGE_PNG } from "@abacus/ui/specimens";
import {
  type FixtureHandler,
  type FixtureRequest,
  json,
  never,
} from "../../app-core/fixture-mode";
import { REVEAL_AT, type SeededCitation, type SeededDocument } from "../seed/trust";

const NOT_FOUND = { detail: "not found" };
const FORBIDDEN = { detail: "forbidden" };

function bytesOf(dataUrl: string): ArrayBuffer {
  const base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  const raw = atob(base64);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out.buffer;
}

function png(face: SeededDocument["face"]): Response {
  return new Response(bytesOf(face === "form" ? FORM_PAGE_PNG : STATEMENT_PAGE_PNG), {
    status: 200,
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function listed(rows: readonly SeededCitation[], query: URLSearchParams): CitationV2Out[] {
  const anchorType = query.get("anchor_type");
  const anchorId = query.get("anchor_id");
  const anchorRef = query.get("anchor_ref");
  const host = query.get("host_ref");
  const section = query.get("section_id");
  const version = query.get("source_version_id");
  const kind = query.get("kind");
  const [hostType, hostId] = host === null ? [null, null] : host.split(":", 2);
  const found = rows.filter(
    ({ anchor, out }) =>
      (anchorType === null || anchor.type === anchorType) &&
      (anchorId === null || anchor.id === anchorId) &&
      (anchorRef === null || anchor.ref === anchorRef) &&
      (host === null || (anchor.type === hostType && anchor.id === hostId)) &&
      (section === null || anchor.section === section) &&
      (version === null || out.source.evidence_version_id === version) &&
      (kind === null || out.kind === kind),
  );
  return found.map((r) => r.out).sort((a, b) => a.n - b.n);
}

export interface TrustFixtures {
  citations: readonly SeededCitation[];
  documents: Readonly<Record<string, SeededDocument>>;
  /** Versions whose manifest never answers (SHL-08e: still processing). */
  loading?: readonly string[];
  /** The reader gets no page images (DEC-369: an offshore member until OCR): the manifest says
   * `view: text`, a page image is refused 403 as the server refuses it, the text is served. */
  textOnly?: boolean;
  /** SHL-08c: the reveal answers 403 `mfa_required` (a stale step-up). */
  revealNeedsMfa?: boolean;
  /** SHL-08d flag off (or a person without `evidence.unlock`): the manifest offers no Unlock. */
  unlockOff?: boolean;
  /** SHL-08d: the next unlock answers 429 `unlock_rate_limited`. */
  unlockLimited?: boolean;
  /** Who the reveal names (the scenario's persona). */
  revealedBy?: string;
}

/** The C4 read routes over `fixtures`. */
export function trustHandlers(fixtures: TrustFixtures): Record<string, FixtureHandler> {
  const doc = (request: FixtureRequest): SeededDocument | undefined =>
    fixtures.documents[request.params.version_id ?? ""];
  // Versions unlocked in this scenario's session (the derivation's manifest from then on).
  const unlocked = new Set<string>();
  let failures = 0;
  return {
    "GET /v1/citations": ({ query }) => {
      const items = listed(fixtures.citations, query);
      return json({ items, total: items.length } satisfies ListPageCitationV2Out);
    },
    "GET /v1/citations/{citation_id}": ({ params }) => {
      const found = fixtures.citations.find((c) => c.out.id === params.citation_id);
      return found === undefined ? json(NOT_FOUND, 404) : json(found.out);
    },
    "GET /v1/evidence-versions/{version_id}/viewer": (request) => {
      if (fixtures.loading?.includes(request.params.version_id ?? "")) return never();
      const found = doc(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const id = request.params.version_id ?? "";
      let manifest =
        unlocked.has(id) && found.unlock !== undefined ? found.unlock.manifest : found.manifest;
      if (fixtures.unlockOff === true) {
        manifest = {
          ...manifest,
          allowed_actions: manifest.allowed_actions.filter((a) => a !== "evidence.unlock"),
        };
      }
      return json(fixtures.textOnly === true ? { ...manifest, view: "text" } : manifest);
    },
    "POST /v1/evidence-versions/{version_id}/pii-reveals": (request) => {
      const found = doc(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (fixtures.textOnly === true) return json(FORBIDDEN, 403);
      if (fixtures.revealNeedsMfa === true) {
        return json({ detail: "forbidden", facts: { reason: "mfa_required" } }, 403);
      }
      const body = (request.body ?? {}) as { region_id?: string };
      const value = found.reveals?.[body.region_id ?? ""];
      if (value === undefined) return json(NOT_FOUND, 404);
      return json(
        {
          mask_id: body.region_id ?? "",
          value: value.value,
          kind: value.kind,
          expires_in: 30,
          revealed_by: fixtures.revealedBy ?? "",
          revealed_at: REVEAL_AT,
        } satisfies PiiRevealOut,
        201,
      );
    },
    "POST /v1/evidence-versions/{version_id}/unlock": (request) => {
      const found = doc(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (found.unlock === undefined || fixtures.unlockOff === true) {
        return json({ detail: "not_password_protected" }, 409);
      }
      if (fixtures.unlockLimited === true || failures >= 5) {
        return json({ detail: "unlock_rate_limited", facts: { limit: 5, retry_after: 600 } }, 429);
      }
      const body = (request.body ?? {}) as { password?: string };
      if (body.password !== found.unlock.password) {
        failures += 1;
        return json({
          status: "wrong_password",
          attempts_left: 5 - failures,
          derivation_id: null,
        } satisfies EvidenceUnlockOut);
      }
      unlocked.add(request.params.version_id ?? "");
      return json({
        status: "ready",
        attempts_left: null,
        derivation_id: found.unlock.manifest.derivation_id,
      } satisfies EvidenceUnlockOut);
    },
    "GET /v1/evidence-versions/{version_id}/pages/{page_no}": (request) => {
      if (fixtures.textOnly === true) return json(FORBIDDEN, 403);
      const found = doc(request);
      const page = Number(request.params.page_no);
      const shown =
        found !== undefined && unlocked.has(request.params.version_id ?? "")
          ? (found.unlock?.manifest ?? found.manifest)
          : found?.manifest;
      if (found === undefined || shown === undefined || !shown.pages.some((p) => p.n === page)) {
        return json(NOT_FOUND, 404);
      }
      return png(found.face);
    },
    "GET /v1/evidence-versions/{version_id}/text": (request) => {
      const found = doc(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const items =
        found.text ??
        found.manifest.pages.map((p) => ({ page: p.n, text: "", unread: p.pii_scan !== "done" }));
      return json({ items, sheets: [], truncated: false } satisfies ViewerTextOut);
    },
    "GET /v1/evidence-versions/{version_id}/regions": (request) => {
      const found = doc(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const wanted = request.query.getAll("match_ids");
      const items =
        wanted.length === 0
          ? found.regions
          : found.regions.filter((r) => wanted.includes(r.match_id));
      return json({ items } satisfies ViewerRegionsOut);
    },
    "GET /v1/evidence-versions/{version_id}/search": (request) => {
      const found = doc(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const q = (request.query.get("q") ?? "").toLowerCase();
      // Rects only, never text: a hit is a region whose label holds the term.
      const items = found.regions
        .filter((r) => q !== "" && (r.label ?? "").toLowerCase().includes(q) && r.page !== null)
        .map((r) => ({ page: r.page ?? 1, rects: r.rects }));
      return json({ items, total: items.length, truncated: false } satisfies ViewerSearchOut);
    },
  };
}
