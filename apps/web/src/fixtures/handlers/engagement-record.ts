// The ENG-02 engagement record routes over the seed (P-07-T20; docs/contracts/engagements-v2.md):
// the v2 record projection, its gates, its work items, and the interim recorded letter (G3 until
// C7). Typed with the generated client. The recorded letter enforces what the live route will:
// 409 `engagement_archived` on an archived record, 409 `gate_unmet` before G1, and 409
// `letter_before_acceptance` when a signature date is not after the acceptance decision; once
// recorded the engagement reads `contracted` and G3 is met. A walled or unknown engagement
// answers 404 (INV-3). The status menu's hold and resume (DEC-328, DEC-344) answer 403 without
// `engagement.hold` in the record's `allowed_actions` or on an archived record, and 409
// `illegal_transition` from any other status. Writes change this handler set's own copy.

import type {
  EngagementGateOut,
  EngagementHoldIn,
  EngagementLetterRecordOut,
  EngagementStatusOut,
  LetterRecordIn,
  TeamMemberOut,
  WorkItemOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { Seed } from "../seed";
import { type EngagementRecordFixture, engagementRecords } from "../seed/engagement-records";
import { slugOf } from "../seed/people";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };

/** The hold route's refusals before the transition: the matrix (403) and archived (403). */
function moveRefused(found: EngagementRecordFixture): Response | null {
  if (found.record.read_only_reason === "archived") {
    return json({ detail: "archived_write" }, 403);
  }
  if (!(found.record.allowed_actions ?? []).includes("engagement.hold")) {
    return json({ detail: "forbidden" }, 403);
  }
  return null;
}

export function engagementRecordHandlers(
  seed: Seed,
  extra: readonly EngagementRecordFixture[] = [],
): Record<string, FixtureHandler> {
  const records = new Map<string, EngagementRecordFixture>(
    [...Object.values(engagementRecords(seed)), ...extra].map((f) => [
      f.record.id,
      structuredClone(f),
    ]),
  );
  const find = (request: FixtureRequest): EngagementRecordFixture | undefined => {
    const found = records.get(request.params.engagement_id ?? "");
    if (found === undefined) return undefined;
    const who = request.persona ?? DEFAULT_PERSONA;
    const walled = seed.walls.some(
      (w) => w.personSlug === who && w.clientId === found.record.client_id,
    );
    return walled ? undefined : found;
  };
  return {
    "GET /v1/engagements/{engagement_id}/record": (request) => {
      const found = find(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(found.record);
    },
    "GET /v1/engagements/{engagement_id}/gates": (request) => {
      const found = find(request);
      const body: EngagementGateOut[] | undefined = found?.record.gates;
      return body === undefined ? json(NOT_FOUND, 404) : json(body);
    },
    "GET /v1/engagements/{engagement_id}/work-items": (request) => {
      const found = find(request);
      if (found !== undefined) return json(found.workItems);
      const id = request.params.engagement_id ?? "";
      const body: WorkItemOut[] | undefined = seed.workItems[id];
      return body === undefined ? json(NOT_FOUND, 404) : json(body);
    },
    // The Team tab host (P-07-T28): the record's team, else the seed engagement's.
    "GET /v1/engagements/{engagement_id}/team": (request) => {
      const found = find(request);
      if (found?.team !== undefined) return json(found.team);
      const id = found?.record.id ?? request.params.engagement_id ?? "";
      const who = request.persona ?? DEFAULT_PERSONA;
      const engagement = seed.engagements.find((e) => e.id === id);
      const walled = seed.walls.some(
        (w) => w.personSlug === who && w.clientId === engagement?.client_id,
      );
      if (engagement === undefined || walled || (found === undefined && records.has(id))) {
        return json(NOT_FOUND, 404);
      }
      const body: TeamMemberOut[] = engagement.team.map((m) => ({
        user_id: m.user_id,
        display_name: m.display_name,
        role: m.role,
      }));
      return json(body);
    },
    "POST /v1/engagements/{engagement_id}/hold": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const refused = moveRefused(found);
      if (refused !== null) return refused;
      if (found.record.status !== "active") return json({ detail: "illegal_transition" }, 409);
      const { reason } = request.body as EngagementHoldIn;
      found.record = {
        ...found.record,
        status: "on_hold",
        hold_reason: reason,
        version: found.record.version + 1,
      };
      const out: EngagementStatusOut = {
        engagement_id: found.record.id,
        status: "on_hold",
        hold_reason: reason,
      };
      return json(out);
    },
    "POST /v1/engagements/{engagement_id}/resume": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const refused = moveRefused(found);
      if (refused !== null) return refused;
      if (found.record.status !== "on_hold") return json({ detail: "illegal_transition" }, 409);
      found.record = {
        ...found.record,
        status: "active",
        hold_reason: null,
        version: found.record.version + 1,
      };
      const out: EngagementStatusOut = { engagement_id: found.record.id, status: "active" };
      return json(out);
    },
    "PUT /v1/engagements/{engagement_id}/letter/record": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const id = found.record.id;
      if (found.record.read_only_reason === "archived") {
        return json({ detail: "engagement_archived", facts: { engagement_id: id } }, 409);
      }
      const g1 = found.record.gates.find((g) => g.gate === "G1");
      if (g1?.met !== true || found.acceptanceDecidedAt === null) {
        return json({ detail: "gate_unmet", facts: { gate: "G1", engagement_id: id } }, 409);
      }
      const body = request.body as LetterRecordIn;
      const decided = found.acceptanceDecidedAt.slice(0, 10);
      const dates = [body.client_signed_on, body.firm_signed_on];
      if (body.mode === "signed") {
        if (dates.some((d) => d == null || d === "")) return json({ detail: "validation" }, 422);
        if (dates.some((d) => (d ?? "") <= decided)) {
          return json({ detail: "letter_before_acceptance", facts: { engagement_id: id } }, 409);
        }
      }
      const who = request.persona ?? DEFAULT_PERSONA;
      const by =
        seed.people.find((p) => p.slug === who)?.userId ?? stableId(`user:${slugOf(who)}`);
      const signedOn = [body.client_signed_on ?? "", body.firm_signed_on ?? ""].sort()[1] ?? null;
      found.record = {
        ...found.record,
        status: "contracted",
        letter: {
          status: "signed",
          signed_on: signedOn,
          signed_count: 2,
          signer_count: 2,
        },
        gates: found.record.gates.map((g) =>
          g.gate === "G3"
            ? {
                gate: "G3",
                met: true,
                met_at: `${signedOn ?? decided}T15:00:00Z`,
                met_by_user_id: by,
              }
            : g,
        ),
        bands: found.record.bands.map((b) => ({
          ...b,
          rows: b.rows.map((r) =>
            r.key === "letter" ? { ...r, on: signedOn, pill_code: "signed" } : r,
          ),
        })),
        version: found.record.version + 1,
      };
      const out: EngagementLetterRecordOut = {
        engagement_id: id,
        mode: body.mode,
        status: "signed",
        client_signed_on: body.client_signed_on ?? null,
        firm_signed_on: body.firm_signed_on ?? null,
        client_signer_contact_id: body.client_signer_contact_id ?? null,
        firm_signer_user_id: body.firm_signer_user_id ?? null,
        signed_copy_version_id: body.signed_copy_version_id ?? null,
        acceptance_decided_at: found.acceptanceDecidedAt,
        recorded_by: by,
        recorded_at: "2026-09-14T14:24:00Z",
        engagement_status: "contracted",
      };
      return json(out);
    },
  };
}
