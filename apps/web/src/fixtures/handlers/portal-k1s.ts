// Fixture handlers for POR-13's portal routes (T-02-T27; docs/contracts/k1-packages.md), over
// seed/portal-k1s.ts. A K-1-only person's `GET /v1/me` answers the reduced `k1` shell; the reads
// answer the artboard's packages; a download answers bytes; a details change is pending.
import type { MeOut, RecipientDetailsChangeOut } from "@abacus/api-client";
import { nowMs } from "../../app-core/clock";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  K1_PERSONAS,
  type Por13Variant,
  k1Me,
  portalK1Detail,
  portalK1Expected,
  portalK1Rows,
} from "../seed/portal-k1s";
import { stableId } from "../seed/prng";

export function portalK1Handlers(
  variant: Por13Variant,
  base: Readonly<Record<string, FixtureHandler>>,
): Record<string, FixtureHandler> {
  const me = base["GET /v1/me"];
  return {
    ...(me === undefined
      ? {}
      : {
          "GET /v1/me": async (request) => {
            const slug = request.persona ?? "";
            if (K1_PERSONAS[slug] === undefined) return me(request);
            // A K-1-only person: the firm's portal user shape, the reduced shell (DEC-129).
            const answered = await me({ ...request, persona: "meera-shah" });
            return json(k1Me((await answered.json()) as MeOut, slug));
          },
        }),
    "GET /v1/portal/k1s": () => json(portalK1Rows(variant)),
    "GET /v1/portal/k1s/expected": () => json(portalK1Expected(variant)),
    "GET /v1/portal/k1s/{package_id}": ({ params }) => {
      const found = portalK1Detail(variant, params.package_id ?? "");
      return found === undefined ? json({ detail: "not_found" }, 404) : json(found);
    },
    "GET /v1/portal/k1s/{package_id}/download": () =>
      new Response(new Blob(["PK"], { type: "application/zip" }), {
        headers: { "Content-Disposition": 'attachment; filename="k1.zip"' },
      }),
    "GET /v1/portal/k1s/{package_id}/attachments/{document_id}": () =>
      new Response(new Blob(["%PDF-1.4"], { type: "application/pdf" }), {
        headers: { "Content-Disposition": 'attachment; filename="k1.pdf"' },
      }),
    "POST /v1/portal/k1-recipients/{recipient_id}/details-changes:upload": ({ params, query }) => {
      const kind = query.get("kind") === "w8" ? "w8" : "w9";
      const out: RecipientDetailsChangeOut = {
        id: stableId(`details-change:${params.recipient_id ?? ""}:${kind}`),
        recipient_id: params.recipient_id ?? "",
        kind,
        status: "pending",
        submitted_at: new Date(nowMs()).toISOString(),
        evidence_version_id: stableId(`details-upload:${params.recipient_id ?? ""}:${kind}`),
      };
      return json(out, 201);
    },
    "POST /v1/portal/k1-recipients/{recipient_id}/details-changes": ({ params, body }) => {
      const given = body as { kind: RecipientDetailsChangeOut["kind"]; upload_id?: string | null };
      const out: RecipientDetailsChangeOut = {
        id: stableId(`details-change:${params.recipient_id ?? ""}:${given.kind}`),
        recipient_id: params.recipient_id ?? "",
        kind: given.kind,
        status: "pending",
        submitted_at: new Date(nowMs()).toISOString(),
        evidence_version_id: given.upload_id ?? null,
      };
      return json(out, 201);
    },
  };
}
