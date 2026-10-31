// C7's portal signing routes in fixture mode for POR-06 (N-02-T26; docs/contracts/c7-envelopes.md
// §2): Owen Calder's envelopes from seed/portal-envelopes.ts. Each scenario owns one copy of the
// envelope, so the writes it answers (the ERSD consent, a signing session, a decline and its
// withdrawal) change only that scenario. The provider's return is a hint: GET …/return answers the
// server's view, which says signed only when the scenario's provider has completed (`signs`).
// N-02-T29: a session before the letter's date answers 409 `before_date_as_of` and a signer whose
// identity checks failed 409 `verification_failed` (DF-11), as C7 does; the list's signed band is
// the scenario's.
import type {
  ListPagePortalEnvelopeRow,
  PortalEnvelopeRow,
  PortalEnvelopeView,
  SignerDeclineIn,
  SigningSessionOut,
} from "@abacus/api-client";
import { STATEMENT_PAGE_PNG } from "@abacus/ui/specimens";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { E13_ROW, E13_SESSION, E13_VIEW, SIGNED_ROWS } from "../seed/portal-envelopes";

const NOT_FOUND = { detail: "not_found" };

export interface PortalEnvelopeOptions {
  /** The envelope as the scenario opens it. */
  view?: PortalEnvelopeView;
  /** The provider completed Owen's signature: the return and every later read say signed. */
  signs?: boolean;
  /** The viewer is not a signer on any envelope (restricted): every read is 404 (no oracle). */
  restricted?: boolean;
  /** The viewer's signed band in the list; default Owen's (E13's persona). */
  signedRows?: readonly PortalEnvelopeRow[];
}

function bytesOf(dataUrl: string): ArrayBuffer {
  const raw = atob(dataUrl.slice(dataUrl.indexOf(",") + 1));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out.buffer;
}

function png(): Response {
  return new Response(bytesOf(STATEMENT_PAGE_PNG), {
    status: 200,
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function signed(view: PortalEnvelopeView): PortalEnvelopeView {
  return {
    ...view,
    row: { ...view.row, status: "partially_signed", my_status: "signed" },
    signers_signed: view.signers_signed + 1,
    signers: view.signers.map((s) => (s.me ? { ...s, status: "signed" as const } : s)),
    signing_session: null,
    outcome: "signed",
  };
}

export function portalEnvelopeHandlers(
  options: PortalEnvelopeOptions = {},
): Record<string, FixtureHandler> {
  let view: PortalEnvelopeView = options.view ?? E13_VIEW;
  // Before a decline: what withdrawing it restores.
  let before: PortalEnvelopeView | null = null;
  const mine = (id: string | undefined): boolean => !options.restricted && id === view.row.id;
  const row = (): PortalEnvelopeRow => view.row;
  return {
    "GET /v1/portal/envelopes": ({ query }) => {
      if (options.restricted) {
        return json({
          items: [],
          next_cursor: null,
          total: 0,
        } satisfies ListPagePortalEnvelopeRow);
      }
      const done = (r: PortalEnvelopeRow): boolean => r.my_status === "signed";
      const all = [row(), ...(options.signedRows ?? SIGNED_ROWS)];
      const wanted = query.get("status");
      const items =
        wanted === "signed"
          ? all.filter(done)
          : wanted === "to_sign"
            ? all.filter((r) => !done(r))
            : all;
      return json({
        items,
        next_cursor: null,
        total: items.length,
      } satisfies ListPagePortalEnvelopeRow);
    },
    "GET /v1/portal/envelopes/{envelope_id}": ({ params }) =>
      mine(params.envelope_id) ? json(view) : json(NOT_FOUND, 404),
    "GET /v1/portal/envelopes/{envelope_id}/documents/{document_id}/pages/{page_no}": ({
      params,
    }) => {
      const doc = view.documents.find((d) => d.id === params.document_id);
      const n = Number(params.page_no);
      if (!mine(params.envelope_id) || doc === undefined || !(n >= 1 && n <= doc.page_count)) {
        return json(NOT_FOUND, 404);
      }
      return png();
    },
    "POST /v1/portal/envelopes/{envelope_id}/viewed": ({ params }) =>
      mine(params.envelope_id) ? json(row()) : json(NOT_FOUND, 404),
    "POST /v1/portal/envelopes/{envelope_id}/progress": ({ params }) =>
      mine(params.envelope_id) ? json(row()) : json(NOT_FOUND, 404),
    "POST /v1/portal/envelopes/{envelope_id}/esign-consent": ({ params, body }) => {
      if (!mine(params.envelope_id)) return json(NOT_FOUND, 404);
      const version = (body as { disclosure_version_id?: string } | null)?.disclosure_version_id;
      if (version !== view.disclosure_version_id) return json({ detail: "stale_disclosure" }, 409);
      view = { ...view, esign_consent_needed: false };
      return json(view);
    },
    "POST /v1/portal/envelopes/{envelope_id}/signing-session": ({ params }) => {
      if (!mine(params.envelope_id)) return json(NOT_FOUND, 404);
      if (view.row.my_status === "verification_failed") {
        return json({ detail: "verification_failed" }, 409);
      }
      if (view.signing_opens_on !== null) {
        return json({ detail: "before_date_as_of", date_as_of: view.signing_opens_on }, 409);
      }
      if (view.esign_consent_needed) return json({ detail: "esign_consent_needed" }, 409);
      view = { ...view, signing_session: E13_SESSION };
      return json(E13_SESSION satisfies SigningSessionOut);
    },
    "GET /v1/portal/envelopes/{envelope_id}/signing-session/{session_id}/return": ({ params }) => {
      if (!mine(params.envelope_id)) return json(NOT_FOUND, 404);
      // A hint: the server's view, signed only once the provider completed (the scenario's).
      if (options.signs === true && view.row.my_status !== "signed") view = signed(view);
      return json(view);
    },
    "POST /v1/portal/envelopes/{envelope_id}/decline": ({ params, body }) => {
      if (!mine(params.envelope_id)) return json(NOT_FOUND, 404);
      const reason = (body as Partial<SignerDeclineIn> | null)?.reason;
      if (reason === undefined) return json({ detail: "reason_required" }, 422);
      before = view;
      view = {
        ...view,
        row: { ...view.row, status: "declined", my_status: "declined" },
        signing_session: null,
        outcome: "declined",
      };
      return json(view);
    },
    "POST /v1/portal/envelopes/{envelope_id}/decline/withdraw": ({ params }) => {
      if (!mine(params.envelope_id)) return json(NOT_FOUND, 404);
      view = before ?? { ...view, row: { ...E13_ROW }, outcome: null };
      before = null;
      return json(view);
    },
  };
}
