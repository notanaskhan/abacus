// The single-client intake routes in fixture mode (P-07-T49; docs/contracts/client-intake.md),
// answering as the live routes do (P-07-T42): one draft per scenario with optimistic versions,
// dedupe by name, per-step validation with registered codes, the conflict check (a walled match
// redacted), a manager's clearing of a counterparty hit, person-recorded screening and the commit
// (Prospect only; `start_acceptance` opens the acceptance record). Typed with the generated client.

import type {
  ClientIntakeDraftOut,
  ClientIntakeDraftPayload,
  ConflictCheckOut,
  IntakeProblemOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };
const DEATH_FORM = "forms_706_709";
const ENGAGEMENT_TYPES = new Set(["forms_706_709", "form_1041", "form_1040"]);

export interface IntakeFixture {
  draft: ClientIntakeDraftOut;
  check: ConflictCheckOut;
  dedupe: { name: string; clientId: string; score: number };
  now: string;
}

/** What a step still lacks, as the server words it (registered codes, never prose). */
export function problemsOf(p: ClientIntakeDraftPayload, step: string): IntakeProblemOut[] {
  const out: IntakeProblemOut[] = [];
  const entity = p.entity ?? null;
  if (step === "entity") {
    if (entity == null) out.push({ field: "entity.mode", code: "required" });
    else if (!entity.entity_name) out.push({ field: "entity.entity_name", code: "required" });
  }
  if (step === "services" || step === "review") {
    const services = p.services ?? [];
    if (services.length === 0) out.push({ field: "services", code: "required" });
    if (services.some((s) => ENGAGEMENT_TYPES.has(s.type_code)) && !p.engagement_partner_user_id) {
      out.push({ field: "engagement_partner_user_id", code: "required" });
    }
    if (services.some((s) => s.type_code === DEATH_FORM) && !entity?.date_of_death) {
      out.push({ field: "entity.date_of_death", code: "date_of_death_required" });
    }
  }
  return out;
}

const OPEN = new Set(["pending", "counterparty_review", "conflict"]);

export function intakeHandlers(f: IntakeFixture): Record<string, FixtureHandler> {
  const mine = (r: FixtureRequest): boolean => r.params.draft_id === f.draft.id;
  return {
    "POST /v1/client-intake-drafts": () => json(f.draft, 201),
    "GET /v1/client-intake-drafts/{draft_id}": (r) =>
      mine(r) ? json(f.draft) : json(NOT_FOUND, 404),
    "PATCH /v1/client-intake-drafts/{draft_id}": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const body = r.body as {
        seen_version?: number;
        step?: ClientIntakeDraftOut["step"];
        payload?: ClientIntakeDraftPayload;
      } | null;
      if (body?.seen_version !== f.draft.version) {
        return json({ detail: "stale_version", facts: { draft_id: f.draft.id } }, 409);
      }
      f.draft = {
        ...f.draft,
        ...(body.step === undefined ? {} : { step: body.step }),
        ...(body.payload === undefined ? {} : { payload: body.payload }),
        version: f.draft.version + 1,
        saved_at: f.now,
      };
      return json(f.draft);
    },
    "POST /v1/client-intake-drafts/{draft_id}/validate": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const step = (r.body as { step?: string } | null)?.step ?? "entity";
      const problems = problemsOf(f.draft.payload, step);
      if (step === "conflicts" || step === "review") {
        if (f.draft.payload.conflict_check_id == null) {
          problems.push({ field: "conflict_check_id", code: "gate_unmet" });
        } else if ((f.check.results ?? []).some((x) => OPEN.has(x.assessment))) {
          problems.push({ field: "conflict_check_id", code: "gate_unmet" });
        }
      }
      return json({ draft_id: f.draft.id, step, problems });
    },
    "POST /v1/clients/dedupe": (r) => {
      const name = ((r.body as { name?: string } | null)?.name ?? "").toLowerCase();
      const hit = name.includes(f.dedupe.name.toLowerCase());
      return json({
        candidates: hit
          ? [
              {
                client_id: f.dedupe.clientId,
                display_name: f.dedupe.name,
                score: f.dedupe.score,
                basis: "name",
              },
            ]
          : [],
      });
    },
    "POST /v1/conflict-checks": () => {
      f.draft = { ...f.draft, payload: { ...f.draft.payload, conflict_check_id: f.check.id } };
      return json(f.check, 201);
    },
    "GET /v1/conflict-checks/{check_id}": (r) =>
      r.params.check_id === f.check.id ? json(f.check) : json(NOT_FOUND, 404),
    "POST /v1/conflict-checks/{check_id}/results/{result_id}/clear": (r) => {
      const result = (f.check.results ?? []).find((x) => x.id === r.params.result_id);
      if (result === undefined) return json(NOT_FOUND, 404);
      if (!(result.allowed_actions ?? []).includes("conflict.clear")) {
        return json({ detail: "forbidden" }, 403);
      }
      Object.assign(result, {
        assessment: "not_adverse",
        cleared_at: f.now,
        cleared_by: stableId("user:samuel-ito"),
        allowed_actions: [],
      });
      return json(result);
    },
    "POST /v1/screening-records": (r) => {
      const body = r.body as { screening_list: string; result: string; subject: unknown };
      return json(
        {
          id: stableId(`screening:${body.screening_list}`),
          screening_list: body.screening_list,
          result: body.result,
          subject: body.subject,
          recorded_by: stableId("user:grace-holloway"),
          recorded_at: f.now,
        },
        201,
      );
    },
    "POST /v1/client-intake-drafts/{draft_id}/commit": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const start = (r.body as { start_acceptance?: boolean } | null)?.start_acceptance === true;
      const engagement = stableId(`engagement:intake:${f.draft.id}`);
      return json(
        {
          draft_id: f.draft.id,
          client_id: f.draft.payload.entity?.client_id ?? stableId(`client:intake:${f.draft.id}`),
          client_entity_id: stableId(`entity:intake:${f.draft.id}`),
          engagement_ids: [engagement],
          work_item_ids: [],
          engagement_status: "prospect",
          conflict_check_id: f.draft.payload.conflict_check_id ?? null,
          acceptance_record_id: start ? stableId(`acceptance:intake:${f.draft.id}`) : null,
        },
        201,
      );
    },
  };
}
