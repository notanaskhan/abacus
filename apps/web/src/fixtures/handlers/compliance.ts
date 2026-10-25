// Fixture handlers for compliance-kernel v1.1 (Q-02-T38; docs/contracts/compliance-kernel.md):
// the firm-export family as its stub fixes it, over the seed's history. `requested` gives ADM-06
// g (Felix Andersen's request waiting for Margaret Okonkwo); a request answers 202 with that
// pending export; only the named approver may approve or decline (409 `approver_must_differ`
// for the requester); a link for an export past its 7 days answers 410 `export_expired`.
import type { FirmExportOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { EXPORT_HISTORY, EXPORT_REQUESTED, firmExportPage } from "../seed/compliance";

const NOT_FOUND = { detail: "not found" };

export function complianceHandlers(
  options: { requested?: boolean; approver?: boolean } = {},
): Record<string, FixtureHandler> {
  let pending: FirmExportOut | null = options.requested === true ? EXPORT_REQUESTED : null;
  const find = (id: string | undefined): FirmExportOut | undefined =>
    [pending, ...EXPORT_HISTORY].find((e) => e !== null && e.id === id) ?? undefined;
  const decide = (id: string | undefined, status: "building" | "declined") => {
    const found = find(id);
    if (found === undefined) return json(NOT_FOUND, 404);
    if (options.approver !== true) return json({ detail: "approver_must_differ" }, 409);
    if (found.status !== "awaiting_approval") {
      return json({ detail: "export_not_awaiting_approval" }, 409);
    }
    pending = { ...found, status, decided_at: found.requested_at };
    return json(pending);
  };
  return {
    "GET /v1/firm/data-exports": () => json(firmExportPage(pending !== null)),
    "POST /v1/firm/data-exports": () => {
      pending = EXPORT_REQUESTED;
      return json(pending, 202);
    },
    "POST /v1/firm/data-exports/{export_id}/approve": ({ params }) =>
      decide(params.export_id, "building"),
    "POST /v1/firm/data-exports/{export_id}/decline": ({ params }) =>
      decide(params.export_id, "declined"),
    "POST /v1/firm/data-exports/{export_id}/link": ({ params }) => {
      const found = find(params.export_id);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (found.status === "expired") return json({ detail: "export_expired" }, 410);
      return json({ detail: "export_not_ready" }, 409);
    },
  };
}
