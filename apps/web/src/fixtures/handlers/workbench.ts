// The workbench-sessions family in fixture mode (W-02-T08; docs/contracts/workbench-sessions.md):
// WB-01's list with its filters, title search and counts, the blank create, rename and soft
// delete, WB-02's picker and context, WB-03's drill and O4 preview, from seed/workbench.ts at E0
// (Mon Sep 14, 2026). Counts are the visible rows' (DEC-43). TAX-08's `?subject_ref=` list keeps
// answering as it did (no fixture), so its scenarios are unchanged.

import type { SessionListOut, SessionSummaryOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  FIRM_WIDE,
  NEW_SESSION,
  actionRequiredDrill,
  artifactPreview,
  attachedContext,
  contextOptions,
  e0Rows,
} from "../seed/workbench";

type Filter = "all" | "mine" | "via_agent" | "running" | "needs_answer";
const FILTERS: readonly Filter[] = ["all", "mine", "via_agent", "running", "needs_answer"];

function filtered(rows: readonly SessionSummaryOut[], filter: Filter, q: string): SessionListOut {
  const text = q.trim().toLowerCase();
  const keep = (r: SessionSummaryOut): boolean => {
    if (filter === "mine" && r.owner?.name !== "Hannah Leclerc") return false;
    if (filter === "via_agent" && r.owner?.via_agent !== true) return false;
    if (filter === "running" && r.running !== true) return false;
    if (filter === "needs_answer" && r.needs_answer !== true) return false;
    return text === "" || r.title.toLowerCase().includes(text);
  };
  const items = rows.filter(keep);
  return {
    items,
    next_cursor: null,
    total: items.length,
    counts: {
      running: rows.filter((r) => r.running === true).length,
      needs_answer: rows.filter((r) => r.needs_answer === true).length,
    },
  };
}

/** The family's handlers over `rows` (the E0 eight by default). */
export function workbenchHandlers(
  rows: readonly SessionSummaryOut[] = e0Rows(),
): Record<string, FixtureHandler> {
  const live = [...rows];
  return {
    "GET /v1/workbench/sessions": ({ query }) => {
      if (query.get("subject_ref") !== null)
        return json({ detail: "no fixture for this route" }, 404);
      const f = query.get("filter");
      const filter = FILTERS.find((x) => x === f) ?? "all";
      return json(filtered(live, filter, query.get("q") ?? ""));
    },
    "POST /v1/workbench/sessions": () => {
      live.unshift(NEW_SESSION);
      return json(NEW_SESSION, 201);
    },
    "PATCH /v1/workbench/sessions/{session_id}": ({ params, body }) => {
      const at = live.findIndex((r) => r.id === params.session_id);
      const found = live[at];
      if (found === undefined) return json({ detail: "not found" }, 404);
      const title = (body as { title: string }).title;
      const next: SessionSummaryOut = {
        ...found,
        title,
        title_source: "manual",
        version: String(Number(found.version ?? "1") + 1),
      };
      live[at] = next;
      return json(next);
    },
    "DELETE /v1/workbench/sessions/{session_id}": ({ params }) => {
      const at = live.findIndex((r) => r.id === params.session_id);
      if (at === -1) return json({ detail: "not found" }, 404);
      live.splice(at, 1);
      return json({ id: params.session_id, deleted_at: "2026-09-14T14:24:00Z" });
    },
    "GET /v1/workbench/context-options": ({ query }) => {
      const tab = query.get("tab");
      if (tab !== "client_record" && tab !== "documents" && tab !== "workpapers")
        return json({ detail: "tab" }, 422);
      return json(contextOptions(tab));
    },
    "POST /v1/workbench/sessions/{session_id}/context": () => json(attachedContext(), 201),
    "DELETE /v1/workbench/sessions/{session_id}/context/{item_id}": ({ params }) => {
      const left = attachedContext().items.filter((i) => i.id !== params.item_id);
      return json(left.length === 0 ? FIRM_WIDE : { ...attachedContext(), items: left });
    },
    "POST /v1/workbench/sessions/{session_id}/drill": () => json(actionRequiredDrill(), 201),
    "GET /v1/run-artifacts/{artifact_id}/preview": ({ query }) =>
      json(artifactPreview(query.get("sheet") ?? "Summary")),
  };
}
