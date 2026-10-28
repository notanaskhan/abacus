// The bulk client import routes in fixture mode (P-07-T54; docs/contracts/intake-import.md),
// answering as the live routes do (P-07-T52, DEC-643): the upload lands in `reviewing` with the
// heading map; a row at or above 90% is merged without a person, the rest wait; a person's
// decision is refused after the run (409 `import_already_run`) and a decision the row does not
// allow is 422 `import_row_invalid`; the run (202) applies every row but the skipped and the
// undecided, and the import reads `importing` once before `done` (the screen's progress pill).
// Typed with the generated client.

import type { ClientImportOut, ClientImportRowOut } from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";

const NOT_FOUND = { detail: "not_found" };

export interface ImportFixture {
  import: ClientImportOut;
  rows: ClientImportRowOut[];
  now: string;
  /** Who decides (the persona's user id). */
  decidedBy: string;
}

function isReview(r: ClientImportRowOut): boolean {
  return r.score != null && r.score < 0.9 && r.best_match_client_id != null;
}

export function importHandlers(f: ImportFixture): Record<string, FixtureHandler> {
  const mine = (r: FixtureRequest): boolean => r.params.import_id === f.import.id;
  let reads = 0;
  return {
    "POST /v1/client-imports": (r) => {
      const name = r.query.get("filename") ?? f.import.file_name;
      const source = r.query.get("source") === "csv" ? "csv" : "cch_axcess_tax_export";
      f.import = { ...f.import, file_name: name, source, stage: "reviewing", started_at: f.now };
      return json(f.import, 201);
    },
    "GET /v1/client-imports/{import_id}": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      if (f.import.stage === "importing") {
        reads += 1;
        if (reads > 1) {
          const skipped = f.rows.filter((x) => x.decision == null || x.decision === "skip");
          const created = f.rows.filter((x) => x.decision === "new" || x.decision === "keep_both");
          f.import = {
            ...f.import,
            stage: "done",
            completed_at: f.now,
            counts: {
              ...f.import.counts,
              imported: f.rows.length - skipped.length,
              skipped: skipped.length,
              new: created.length,
              failed: 0,
            },
            allowed_actions: [],
          };
        }
      }
      return json(f.import);
    },
    "GET /v1/client-imports/{import_id}/rows": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const items = r.query.get("review") === "true" ? f.rows.filter(isReview) : f.rows;
      const limit = Number(r.query.get("limit") ?? "50");
      return json({ items: items.slice(0, limit), next_cursor: null, total: items.length });
    },
    "PUT /v1/client-imports/{import_id}/rows/{row_id}/decision": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      if (f.import.stage !== "reviewing") {
        return json({ detail: "import_already_run", facts: { import_id: f.import.id } }, 409);
      }
      const row = f.rows.find((x) => x.id === r.params.row_id);
      if (row === undefined) return json(NOT_FOUND, 404);
      const body = r.body as { decision?: ClientImportRowOut["decision"] } | null;
      const decision = body?.decision ?? null;
      if ((decision === "merge" || decision === "keep_both") && row.best_match_client_id == null) {
        return json({ detail: "import_row_invalid", facts: { field: "decision" } }, 422);
      }
      Object.assign(row, { decision, decided_by: f.decidedBy });
      return json(row);
    },
    "POST /v1/client-imports/{import_id}/run": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      if (f.import.stage !== "reviewing") {
        return json({ detail: "import_already_run", facts: { import_id: f.import.id } }, 409);
      }
      f.import = { ...f.import, stage: "importing" };
      reads = 0;
      return json(f.import, 202);
    },
  };
}
