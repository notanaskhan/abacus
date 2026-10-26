// Fixture handlers for the audit-log contract v1 (G-02-T04; docs/contracts/audit-log.md): ADM-07
// as the live routes will answer it. The Actor filter `via_agent` gives b ("4 of 1,962"); a
// search with no match gives f; an IP filters to that IP; `since_seq` lists newer events oldest
// first; the drawer resolves values for Margaret Okonkwo only (DEC-60); an export answers 202 and
// is ready at once (e → g). Nothing here changes or removes an event.
import type { AuditEventRow, AuditExport } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  type AuditView,
  AUDIT_TOTAL,
  EXPORT_READY,
  VIA_AGENT_TOTAL,
  detail,
  feed,
  page,
} from "../seed/audit-log";

const NOT_FOUND = { detail: "not found" };

function searchable(row: AuditEventRow): string {
  const actor = row.actor;
  return [
    actor.person?.display_name,
    actor.on_behalf_of?.display_name,
    actor.policy_ref,
    row.target.label,
    ...Object.values(row.detail_facts ?? {}).map((v) => (typeof v === "string" ? v : "")),
  ]
    .filter((v): v is string => typeof v === "string")
    .join(" ")
    .toLowerCase();
}

export function auditLogHandlers(view: AuditView = "default"): Record<string, FixtureHandler> {
  let exported: AuditExport | null = null;
  return {
    "GET /v1/audit-events": ({ query }) => {
      if (query.get("cursor") !== null) return json(page([], AUDIT_TOTAL, view, false));
      let rows = feed(view);
      const kind = query.get("actor_kind");
      const q = query.get("q")?.trim().toLowerCase() ?? "";
      const ip = query.get("ip");
      const since = query.get("since_seq");
      if (kind !== null) rows = rows.filter((r) => r.actor.kind === kind);
      if (ip !== null) rows = rows.filter((r) => r.ip === ip);
      if (q !== "") rows = rows.filter((r) => searchable(r).includes(q));
      if (since !== null) {
        const after = rows.filter((r) => r.seq > Number(since)).reverse();
        return json(page(after, after.length, view, false));
      }
      const filtered = kind !== null || ip !== null || q !== "";
      const total =
        kind === "via_agent" && ip === null && q === "" ? VIA_AGENT_TOTAL : rows.length;
      return json(
        page(rows, filtered ? total : AUDIT_TOTAL, view, total > rows.length || !filtered),
      );
    },
    "GET /v1/audit-events/exports/{export_id}": ({ params }) =>
      exported !== null && exported.id === params.export_id
        ? json(exported)
        : json(NOT_FOUND, 404),
    "GET /v1/audit-events/{seq}": ({ params, persona }) => {
      const found = detail(Number(params.seq), persona, view);
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    "POST /v1/audit-events/exports": () => {
      exported = EXPORT_READY;
      return json(exported, 202);
    },
    "POST /v1/audit-events/exports/{export_id}/link": ({ params }) =>
      exported !== null && exported.id === params.export_id
        ? json({
            url: "https://exports.invalid/audit-log-2026-09-08-2026-09-14.csv",
            expires_at: "2026-09-14T14:39:00Z",
            manifest_sha256: exported.manifest_sha256 ?? "0".repeat(64),
          })
        : json(NOT_FOUND, 404),
  };
}
